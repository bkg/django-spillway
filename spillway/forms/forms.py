from django.contrib.gis import gdal, forms
from django.contrib.gis.db.models.sql.query import ALL_TERMS
from greenwich.srs import transform_tile

from spillway import styles
from spillway.forms import fields


class SpatialQueryForm(forms.Form):
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


class GeometryQueryForm(forms.Form):
    """A form providing GeoQuerySet method arguments."""
    # Tolerance value for geometry simplification
    simplify = forms.FloatField(required=False)
    srs = fields.SpatialReferenceField(required=False)


class RasterQueryForm(forms.Form):
    """Validates format options for raster data."""
    bbox = fields.BoundingBoxField(required=False)
    g = fields.OGRGeometryField(required=False)
    upload = fields.GeometryFileField(required=False)

    def clean(self):
        """Return cleaned fields as a dict, determine which geom takes
        precedence.
        """
        cleaned = super(RasterQueryForm, self).clean()
        cleaned['g'] = (cleaned.pop('upload') or cleaned.pop('g') or
                        cleaned.pop('bbox'))
        return cleaned


class MapTile(forms.Form):
    """Validates requested map tiling parameters."""
    bbox = fields.OGRGeometryField(required=False)
    x = forms.IntegerField()
    y = forms.IntegerField()
    z = forms.IntegerField()
    size = forms.IntegerField(required=False, initial=256)
    style = forms.ChoiceField(
        choices=[(k, k.lower()) for k in list(styles.colors)],
        required=False)

    def clean(self):
        cleaned = super(MapTile, self).clean()
        x, y, z = map(cleaned.get, ('x', 'y', 'z'))
        # Create bbox from NW and SE tile corners.
        extent = transform_tile(x, y, z) + transform_tile(x + 1, y + 1, z)
        geom = gdal.OGRGeometry.from_bbox(extent)
        geom.srid = self.fields['bbox'].default_srid
        cleaned['bbox'] = geom
        return cleaned
