from django.contrib.gis import forms
from django.contrib.gis.db.models.sql.query import ALL_TERMS

from spillway.forms.fields import BoundingBoxField, SpatialReferenceField


class SpatialQueryForm(forms.Form):
    """Validates bounding box, serves as a common base for raster/vector
    data.
    """
    bbox = BoundingBoxField(required=False)


class GeometryQueryForm(SpatialQueryForm):
    """Validates vector data options."""
    geom = forms.GeometryField(required=False)
    # Tolerance value for geometry simplification
    simplify = forms.FloatField(required=False)
    srs = SpatialReferenceField(required=False)

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
