"""Serializer fields"""
from django.contrib.gis import forms
from rest_framework.fields import FileField, WritableField
from greenwich.raster import Raster

from spillway.compat import json


class GeometryField(WritableField):
    type_name = 'GeometryField'
    type_label = 'geometry'
    form_field_class = forms.GeometryField

    def initialize(self, *args, **kwargs):
        super(GeometryField, self).initialize(*args, **kwargs)
        view = self.context.get('view')
        # Alter the field source based on geometry output format.
        if view and not view.wants_default_renderer():
            renderer = view.request.accepted_renderer
            self.source = renderer.format

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


class NDArrayField(FileField):
    type_name = 'NDArrayField'
    type_label = 'ndarray'

    def to_native(self, value):
        params = self.context.get('params', {})
        geom = params.get('g')
        with Raster(getattr(value, 'path', value)) as r:
            arr = r.clip(geom).masked_array() if geom else r.array()
        return arr.tolist()
