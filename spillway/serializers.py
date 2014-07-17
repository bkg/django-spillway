from django.contrib.gis import forms
from django.contrib.gis.db import models
from rest_framework import serializers
from rest_framework.settings import api_settings


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
        fields[self.opts.geom_field] = serializers.Field(**kwargs)
        return fields
