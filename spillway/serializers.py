from django.contrib.gis import forms
from django.contrib.gis.db import models
from django.contrib.gis.geos import geometry
from rest_framework import serializers
from rest_framework.settings import api_settings

from spillway.compat import json


class GeometryField(serializers.WritableField):
    type_name = 'GeometryField'
    type_label = 'geometry'
    form_field_class = forms.GeometryField

    def to_native(self, value):
        try:
            return {'type': value.geom_type, 'coordinates': value.coords}
        # Value is already serialized as geojson, kml, etc.
        except AttributeError:
            return value


class GeoModelSerializerOptions(serializers.ModelSerializerOptions):
    def __init__(self, meta):
        super(GeoModelSerializerOptions, self).__init__(meta)
        self.geom_field = getattr(meta, 'geom_field', None)


class GeoModelSerializer(serializers.ModelSerializer):
    """Serializer class for GeoModels."""
    _options_class = GeoModelSerializerOptions

    def get_default_fields(self):
        """Returns a fields dict for this serializer with a 'geometry' field
        added.
        """
        fields = super(GeoModelSerializer, self).get_default_fields()
        renderer = getattr(self.context.get('request'),
                           'accepted_renderer', None)
        kwargs = {}
        # Alter the geometry field source based on format.
        if renderer and not isinstance(
                renderer, tuple(api_settings.DEFAULT_RENDERER_CLASSES)):
            kwargs.update(source=renderer.format)
        # Go hunting for a geometry field when it's undeclared.
        if not self.opts.geom_field:
            meta = self.opts.model._meta
            for field in meta.fields:
                if hasattr(field, 'srid'):
                    self.opts.geom_field = field.name
        fields[self.opts.geom_field] = GeometryField(**kwargs)
        return fields


class FeatureSerializer(GeoModelSerializer):
    def to_native(self, obj):
        native = super(FeatureSerializer, self).to_native(obj)
        geomfield = getattr(obj, self.opts.geom_field)
        geometry = native.pop(self.opts.geom_field)
        return {'type': 'Feature',
                'id': native.pop(obj._meta.pk.name, None),
                'geometry': geometry,
                'properties': native}

    def from_native(self, obj, files=None):
        data = {self.opts.geom_field: obj.get('geometry')}
        data.update(obj.get('properties'))
        return super(FeatureSerializer, self).from_native(data, files)

    def restore_object(self, attrs, instance=None):
        geom_field = self.opts.geom_field
        g = attrs[geom_field]
        if isinstance(g, dict):
            attrs.update({geom_field: json.dumps(g)})
        return super(FeatureSerializer, self).restore_object(attrs, instance)