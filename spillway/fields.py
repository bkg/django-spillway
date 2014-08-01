"""Serializer fields"""
from django.contrib.gis import forms
from rest_framework.fields import WritableField

from spillway.compat import json


class GeometryField(WritableField):
    type_name = 'GeometryField'
    type_label = 'geometry'
    form_field_class = forms.GeometryField

    def to_native(self, value):
        # Create a dict from the GEOSGeometry when the value is not previously
        # serialized from the spatial db.
        try:
            return {'type': value.geom_type, 'coordinates': value.coords}
        # Value is already serialized as geojson, kml, etc.
        except AttributeError:
            return value

    def from_native(self, value):
        # forms.GeometryField cannot handle geojson dicts.
        if isinstance(value, dict):
            value = json.dumps(value)
        return super(GeometryField, self).from_native(value)
