"""Serializer fields"""
from django.contrib.gis import forms
from rest_framework.fields import Field, FileField
from greenwich import Raster

from spillway.compat import json


class GeometryField(Field):
    def to_internal_value(self, data):
        # forms.GeometryField cannot handle geojson dicts.
        if isinstance(data, dict):
            data = json.dumps(data)
        return forms.GeometryField().to_python(data)

    def to_representation(self, value):
        # Create a dict from the GEOSGeometry when the value is not previously
        # serialized from the spatial db.
        try:
            return {'type': value.geom_type, 'coordinates': value.coords}
        # Value is already serialized as geojson, kml, etc.
        except AttributeError:
            return value


class NDArrayField(FileField):
    def to_representation(self, value):
        params = self.context.get('params', {})
        geom = params.get('g')
        with Raster(getattr(value, 'path', value)) as r:
            if not geom:
                return r.array().tolist()
            with r.clip(geom) as clipped:
                return clipped.array().tolist()
