from django.contrib.gis import gdal, forms
from django.contrib.gis.db.models import functions
from django.contrib.gis.db.models.lookups import gis_lookups
from greenwich import tile
from rest_framework import renderers

from spillway import query
from spillway.renderers import CSVRenderer, GeoTIFFZipRenderer
from . import fields


class QuerySetForm(forms.Form):
    """Base form for applying GeoQuerySet methods and filters."""

    def __init__(self, data=None, queryset=None, *args, **kwargs):
        super(QuerySetForm, self).__init__(data, *args, **kwargs)
        self.queryset = queryset
        self._is_selected = False

    @classmethod
    def from_request(cls, request, queryset=None, view=None):
        data = (request.query_params.dict() or
                request.data and request.data.dict())
        params = dict(data, **getattr(view, 'kwargs', {}))
        params['format'] = request.accepted_renderer.format
        return cls(params, queryset, files=request.FILES)

    def query(self, force=False):
        """Returns the filtered/selected GeoQuerySet."""
        if not self.is_valid():
            raise forms.ValidationError(self.errors)
        if force:
            self._is_selected = False
        if not self._is_selected:
            if self.queryset is None:
                raise TypeError('Must be QuerySet not %s' %
                                type(self.queryset))
            self.select()
            self._is_selected = True
        return self.queryset

    def select(self):
        """Set GeoQuerySet from field values and filters.

        Subclasses may override this. Not called directly, use .query().
        """
        self.queryset = self.queryset.filter(**self.cleaned_data)


class SpatialQueryForm(QuerySetForm):
    """A Form for spatial lookup queries such as intersects, overlaps, etc.

    Includes 'bbox' as an alias for 'bboverlaps'.
    """
    bbox = fields.BoundingBoxField(required=False)

    def __init__(self, *args, **kwargs):
        super(SpatialQueryForm, self).__init__(*args, **kwargs)
        for lookup in self.data:
            if lookup in gis_lookups:
                self.fields[lookup] = fields.GeometryField(
                    required=False, widget=forms.BaseGeometryWidget())
                break

    def clean(self):
        cleaned_data = super(SpatialQueryForm, self).clean()
        spatial_lookup = set(cleaned_data.keys()) - {'bbox'}
        bbox = cleaned_data.pop('bbox', None)
        # Look for "bbox" which is just an alias to "bboverlaps".
        if bbox:
            cleaned_data.pop(spatial_lookup, None)
            cleaned_data['bboverlaps'] = bbox
        return cleaned_data

    def select(self):
        self.queryset = query.filter_geometry(
            self.queryset, **self.cleaned_data)


class GeometryQueryForm(QuerySetForm):
    """A form providing GeoQuerySet method arguments."""
    format = fields.GeoFormatField(required=False)
    op = fields.GeoFormatField(required=False)
    precision = forms.IntegerField(required=False)
    # Tolerance value for geometry simplification
    simplify = forms.FloatField(required=False)
    srs = fields.SpatialReferenceField(required=False)

    def select(self):
        kwargs = {}
        data = self.cleaned_data
        tolerance, srs, format = map(data.get, ('simplify', 'srs', 'format'))
        expr = field = query.geo_field(self.queryset).name
        srid = getattr(srs, 'srid', None)
        if srid:
            expr = functions.Transform(expr, srid)
            self.queryset.query.add_context('transformed_srid', srid)
        if data['op']:
            expr = data['op'](expr)
        if data['precision'] is not None:
            kwargs.update(precision=data['precision'])
        if tolerance:
            expr = query.Simplify(expr, tolerance)
        if format:
            expr = format(expr, **kwargs)
        if expr != field:
            attrname = self.data.get('format')
            self.queryset = self.queryset.annotate(**{attrname: expr})


class RasterQueryForm(QuerySetForm):
    """Validates format options for raster data."""
    bbox = fields.BoundingBoxField(required=False)
    format = forms.CharField(required=False)
    g = fields.OGRGeometryField(srid=4326, required=False)
    upload = fields.GeometryFileField(required=False)
    periods = forms.IntegerField(required=False)
    stat = forms.ChoiceField(
        choices=[(choice,) * 2 for choice in
                 ('count', 'max', 'mean', 'median', 'min', 'std', 'sum', 'var')],
        required=False)

    def clean(self):
        """Return cleaned fields as a dict, determine which geom takes
        precedence.
        """
        data = super(RasterQueryForm, self).clean()
        geom = data.pop('upload', None) or data.pop('bbox', None)
        if geom:
            data['g'] = geom
        return data

    def select(self):
        txtformats = (renderers.JSONRenderer.format, CSVRenderer.format)
        htmlformats = (renderers.BrowsableAPIRenderer.format,
                       renderers.TemplateHTMLRenderer.format)
        fields = ('format', 'g', 'stat', 'periods')
        format, geom, stat, periods = map(self.cleaned_data.get, fields)
        if not geom and format in htmlformats + txtformats:
            return
        elif geom and format in htmlformats:
            format = txtformats[0]
        if format in txtformats:
            qs = self.queryset.summarize(geom, stat)
        else:
            qs = self.queryset.warp(format=format, geom=geom)
            if GeoTIFFZipRenderer.format[-3:] in format:
                qs = qs.zipfiles()
        if periods:
            qs = qs.aggregate_periods(periods)
        self.queryset = qs


class TileForm(QuerySetForm):
    """Validates requested map tiling parameters."""
    bbox = fields.OGRGeometryField(srid=4326, required=False)
    size = forms.IntegerField(required=False, initial=256)
    x = forms.IntegerField()
    y = forms.IntegerField()
    z = forms.IntegerField()

    def clean(self):
        data = super(TileForm, self).clean()
        x, y, z = map(data.get, ('x', 'y', 'z'))
        # Create bbox from NW and SE tile corners.
        try:
            extent = (tile.to_lonlat(x, y, z) +
                      tile.to_lonlat(x + 1, y + 1, z))
        except ValueError:
            extent = (0, 0, 0, 0)
        geom = gdal.OGRGeometry.from_bbox(extent)
        geom.srid = self.fields['bbox'].srid
        data['bbox'] = geom
        return data


class RasterTileForm(TileForm):
    band = forms.IntegerField(required=False, initial=1)
    size = forms.IntegerField(required=False, initial=256)
    limits = fields.CommaSepFloatField(required=False)
    style = forms.CharField(required=False)

    def clean_band(self):
        return self.cleaned_data['band'] or self.fields['band'].initial

    def clean_style(self):
        # Mapnik requires string, not unicode, for style names.
        return str(self.cleaned_data['style'])


class VectorTileForm(TileForm):
    clip = forms.BooleanField(required=False, initial=True)
    format = forms.CharField(required=False)

    def select(self):
        data = self.cleaned_data
        self.queryset = self.queryset.tile(
            data['bbox'], data['z'], data['format'], data['clip'])
