from django.contrib.gis import forms
from django.contrib.gis.db.models.sql.query import ALL_TERMS

from spillway.forms import fields


class SpatialQueryForm(forms.Form):
    """Base spatial query form."""
    bbox = fields.BoundingBoxField(required=False)


class GeometryQueryForm(SpatialQueryForm):
    """Geometry filter and spatial lookup query form."""
    geom = forms.GeometryField(required=False)
    # Tolerance value for geometry simplification
    simplify = forms.FloatField(required=False)
    srs = fields.SpatialReferenceField(required=False)

    def __init__(self, *args, **kwargs):
        super(GeometryQueryForm, self).__init__(*args, **kwargs)
        self._spatial_lookup = None
        self._set_spatial_lookup()

    def _set_spatial_lookup(self):
        geom_field = self['geom']
        fieldname = geom_field.name
        for lookup in self.data:
            if lookup in ALL_TERMS:
                self._spatial_lookup = lookup
                field = self.fields.pop(fieldname)
                self.fields.update({lookup: field})
                break

    def clean(self):
        cleaned_data = super(GeometryQueryForm, self).clean()
        # Look for "bbox" which is just an alias to "bboverlaps".
        if cleaned_data.get('bbox'):
            cleaned_data.pop(self._spatial_lookup, None)
            self._spatial_lookup = 'bboverlaps'
            cleaned_data[self._spatial_lookup] = cleaned_data.pop('bbox')
        return cleaned_data

    @property
    def cleaned_geodata(self):
        if not (self.is_valid() and self._spatial_lookup):
            return {}
        return {self._spatial_lookup: self.cleaned_data[self._spatial_lookup]}


class RasterQueryForm(SpatialQueryForm):
    """Validates format options for raster data."""
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
