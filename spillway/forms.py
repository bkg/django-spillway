from django.contrib.gis import forms
from django.contrib.gis.db import models
from spillway.fields import BoundingBoxField, SpatialReferenceField


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
        for k in self.data:
            if k.startswith(fieldname):
                name, lookup = k.split('_')
                if lookup in models.sql.query.ALL_TERMS:
                    slkey = '%s__%s' % (name, lookup)
                    self._spatial_lookup = slkey
                    field = self.fields.pop(fieldname)
                    self.fields.update({slkey: field})
                    # QueryDict is immutable, get a mutable copy.
                    try:
                        data = self.data.dict()
                    except AttributeError:
                        data = self.data
                    data[slkey] = data.pop(k)
                    self.data = data
                    break

    @property
    def cleaned_geodata(self):
        if not (self.is_valid() and self._spatial_lookup):
            return {}
        return {self._spatial_lookup: self.cleaned_data[self._spatial_lookup]}
