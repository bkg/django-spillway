"""Serializer fields"""
from django.contrib.gis import forms
from rest_framework.fields import FileField, WritableField
from greenwich.raster import Raster

from spillway.compat import json


class GeometryField(WritableField):
    type_name = 'GeometryField'
    type_label = 'geometry'
    form_field_class = forms.GeometryField
    # TODO: Introspect available formats from spatial backends.
    _formats = ('geohash', 'geojson', 'gml', 'kml', 'svg')

    def set_default_source(self):
        """Set a default source based on the selected renderer."""
        # Do not override an explicitly provided field source.
        if self.source:
            return
        view = self.context.get('view')
        # Alter the field source based on geometry output format.
        try:
            wants_default_renderer = view.wants_default_renderer()
        except AttributeError:
            wants_default_renderer = True
        # Alter the field source based on geometry output format.
        if not wants_default_renderer:
            renderer = view.request.accepted_renderer
            if renderer.format in self._formats:
                self.source = renderer.format
                # Single objects must use GEOSGeometry attrs to provide formats.
                if not self.parent.many:
                    self.source = '%s.%s' % (self.label, self.source)

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
            if not geom:
                return r.array().tolist()
            with r.clip(geom) as clipped:
                return clipped.array().tolist()
