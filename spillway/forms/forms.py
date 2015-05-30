import math

from django.contrib.gis import gdal, forms
from greenwich.srs import transform_tile

from spillway import query, styles
from spillway.compat import ALL_TERMS
from spillway.forms import fields


class GeoQuerySetForm(forms.Form):
    """Base form for applying GeoQuerySet methods and filters."""

    def __init__(self, data=None, queryset=None, *args, **kwargs):
        super(GeoQuerySetForm, self).__init__(data, *args, **kwargs)
        self.queryset = queryset
        self._is_selected = False

    def query(self):
        """Returns the filtered/selected GeoQuerySet."""
        if not self.is_valid():
            raise ValueError('Invalid field values')
        if not self._is_selected:
            if self.queryset is None:
                raise TypeError('Must be GeoQuerySet not %s' %
                                type(self.queryset))
            self.select()
            self._is_selected = True
        return self.queryset

    def select(self):
        """Set GeoQuerySet from field values and filters.

        Subclasses implement this. Not called directly, use .select().
        """
        raise NotImplementedError


class SpatialQueryForm(GeoQuerySetForm):
    """A Form for spatial lookup queries such as intersects, overlaps, etc.

    Includes 'bbox' as an alias for 'bboverlaps'.
    """
    bbox = fields.BoundingBoxField(required=False)

    def __init__(self, *args, **kwargs):
        super(SpatialQueryForm, self).__init__(*args, **kwargs)
        for lookup in self.data:
            if lookup in ALL_TERMS:
                self.fields[lookup] = forms.GeometryField(required=False)
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


class GeometryQueryForm(GeoQuerySetForm):
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


class RasterQueryForm(forms.Form):
    """Validates format options for raster data."""
    bbox = fields.BoundingBoxField(required=False)
    g = fields.OGRGeometryField(required=False)
    upload = fields.GeometryFileField(required=False)
    periods = forms.IntegerField(required=False)
    stat = forms.ChoiceField(
        choices=[(choice,) * 2 for choice in 'max', 'mean', 'min', 'std'],
        required=False)

    def clean(self):
        """Return cleaned fields as a dict, determine which geom takes
        precedence.
        """
        cleaned = super(RasterQueryForm, self).clean()
        cleaned['g'] = (cleaned.pop('upload') or cleaned.pop('bbox') or
                        cleaned.get('g'))
        return cleaned


class MapTile(GeoQuerySetForm):
    """Validates requested map tiling parameters."""
    bbox = fields.OGRGeometryField(srid=4326, required=False)
    clip = forms.BooleanField(required=False, initial=False)
    x = forms.IntegerField()
    y = forms.IntegerField()
    z = forms.IntegerField()
    band = forms.IntegerField(required=False, initial=1)
    size = forms.IntegerField(required=False, initial=256)
    style = forms.ChoiceField(
        choices=[(k, k.lower()) for k in list(styles.colors)],
        required=False)
    # Tile grid uses 3857, but coordinates should be in 4326 commonly.
    tile_srid = 3857
    # Geometry simplification tolerances based on tile zlevel, see
    # http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames.
    #SpatialReference(3857).GetSemiMajor() == 6378137.0
    tolerances = [6378137 * 2 * math.pi / (2 ** (zoom + 8))
                  for zoom in range(20)]

    def clean(self):
        cleaned = super(MapTile, self).clean()
        x, y, z = map(cleaned.get, ('x', 'y', 'z'))
        # Create bbox from NW and SE tile corners.
        extent = transform_tile(x, y, z) + transform_tile(x + 1, y + 1, z)
        geom = gdal.OGRGeometry.from_bbox(extent)
        geom.srid = self.fields['bbox'].srid
        cleaned['bbox'] = geom
        return cleaned

    def select(self):
        data = self.cleaned_data
        bbox = data['bbox']
        geom_wkt = bbox.ewkt
        coord_srid = bbox.srid
        original_srid = self.queryset.geo_field.srid
        try:
            tolerance = self.tolerances[data['z']]
        except IndexError:
            tolerance = self.tolerances[-1]
        attrname = query.geo_field(self.queryset).name
        self.queryset = query.filter_geometry(self.queryset,
                                              intersects=geom_wkt)
        if data['clip']:
            self.queryset = self.queryset.intersection(geom_wkt)
            attrname = 'intersection'
        for obj in self.queryset:
            geom = getattr(obj, attrname)
            # Geometry must be in Web Mercator for simplification.
            if geom.srid != self.tile_srid:
                # Result of intersection does not have SRID set properly.
                if geom.srid is None:
                    geom.srid = original_srid
                geom.transform(self.tile_srid)
            geom = geom.simplify(tolerance, preserve_topology=True)
            geom.transform(coord_srid)
            obj.geojson = geom.geojson
