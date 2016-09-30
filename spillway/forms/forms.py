import math

from django.contrib.gis import gdal, forms
from greenwich.srs import transform_tile

from spillway import query
from spillway.compat import ALL_TERMS
from . import fields


class QuerySetForm(forms.Form):
    """Base form for applying GeoQuerySet methods and filters."""

    def __init__(self, data=None, queryset=None, *args, **kwargs):
        super(QuerySetForm, self).__init__(data, *args, **kwargs)
        self.queryset = queryset
        self._is_selected = False

    @classmethod
    def from_request(cls, request, queryset=None, view=None):
        params = dict(request.query_params.dict(),
                      **getattr(view, 'kwargs', {}))
        params['format'] = request.accepted_renderer.format
        return cls(params, queryset)

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

        Subclasses implement this. Not called directly, use .query().
        """
        raise NotImplementedError


class SpatialQueryForm(QuerySetForm):
    """A Form for spatial lookup queries such as intersects, overlaps, etc.

    Includes 'bbox' as an alias for 'bboverlaps'.
    """
    bbox = fields.BoundingBoxField(required=False)

    def __init__(self, *args, **kwargs):
        super(SpatialQueryForm, self).__init__(*args, **kwargs)
        for lookup in self.data:
            if lookup in ALL_TERMS:
                self.fields[lookup] = fields.GeometryField(required=False)
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
    format = forms.CharField(required=False)
    precision = forms.IntegerField(required=False, initial=4)
    # Tolerance value for geometry simplification
    simplify = forms.FloatField(required=False)
    srs = fields.SpatialReferenceField(required=False)

    def clean_precision(self):
        # Unfortunately initial values are not used as default values.
        return (self.cleaned_data['precision'] or
                self.fields['precision'].initial)

    def select(self):
        data = self.cleaned_data
        kwargs = {'precision': data['precision']}
        tolerance, srs, format = map(data.get, ('simplify', 'srs', 'format'))
        srid = getattr(srs, 'srid', None)
        try:
            has_format = self.queryset.has_format(format)
        except AttributeError:
            # Handle default GeoQuerySet.
            try:
                self.queryset = getattr(self.queryset, format)(**kwargs)
            except AttributeError:
                pass
        else:
            if has_format:
                kwargs.update(format=format)
            self.queryset = self.queryset.simplify(tolerance, srid, **kwargs)


class RasterQueryForm(QuerySetForm):
    """Validates format options for raster data."""
    bbox = fields.BoundingBoxField(required=False)
    format = forms.CharField(required=False)
    g = fields.OGRGeometryField(required=False)
    upload = fields.GeometryFileField(required=False)
    periods = forms.IntegerField(required=False)
    stat = forms.ChoiceField(
        choices=[(choice,) * 2 for choice in
                 'count', 'max', 'mean', 'median', 'min', 'std', 'var'],
        required=False)

    def clean(self):
        """Return cleaned fields as a dict, determine which geom takes
        precedence.
        """
        data = super(RasterQueryForm, self).clean()
        data['g'] = data.pop('upload') or data.pop('bbox') or data.get('g')
        return data

    def select(self):
        format, geom, stat, periods = map(self.cleaned_data.get,
                                          ('format', 'g', 'stat', 'periods'))
        if format in ('csv', 'json'):
            if not geom:
                return
            qs = self.queryset.summarize(geom, stat)
        else:
            qs = self.queryset.warp(format, geom=geom)
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
            extent = (transform_tile(x, y, z) +
                      transform_tile(x + 1, y + 1, z))
        except TypeError:
            pass
        else:
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
    clip = forms.BooleanField(required=False, initial=False)
    format = forms.CharField(required=False)
    # Geometry simplification tolerances based on tile zlevel, see
    # http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames.
    tolerances = [6378137 * 2 * math.pi / (2 ** (zoom + 8))
                  for zoom in range(20)]

    def select(self):
        data = self.cleaned_data
        try:
            tolerance = self.tolerances[data['z']]
        except IndexError:
            tolerance = self.tolerances[-1]
        self.queryset = self.queryset.tile(
            data['bbox'], tolerance, data['format'], data['clip'])
