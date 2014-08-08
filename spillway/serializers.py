from django.contrib.gis.db import models
from rest_framework import serializers

from spillway.collections import Feature
from spillway.fields import GeometryField, NDArrayField
from spillway.models import RasterStore


class GeoModelSerializerOptions(serializers.ModelSerializerOptions):
    def __init__(self, meta):
        super(GeoModelSerializerOptions, self).__init__(meta)
        self.geom_field = getattr(meta, 'geom_field', None)


class GeoModelSerializer(serializers.ModelSerializer):
    """Serializer class for GeoModels."""
    _options_class = GeoModelSerializerOptions
    field_mapping = dict({models.GeometryField: GeometryField},
                         **serializers.ModelSerializer.field_mapping)

    def get_default_fields(self):
        """Returns a fields dict for this serializer with a 'geometry' field
        added.
        """
        fields = super(GeoModelSerializer, self).get_default_fields()
        # Go hunting for a geometry field when it's undeclared.
        if not self.opts.geom_field:
            meta = self.opts.model._meta
            for field in meta.fields:
                if isinstance(field, models.GeometryField):
                    self.opts.geom_field = field.name
                elif isinstance(field, models.FileField):
                    setattr(self.opts, 'raster_field', field.name)
        return fields


class FeatureSerializer(GeoModelSerializer):
    def to_native(self, obj):
        native = super(FeatureSerializer, self).to_native(obj)
        geometry = native.pop(self.opts.geom_field)
        pk = native.pop(obj._meta.pk.name, None)
        return Feature(pk, geometry, native)

    def from_native(self, obj, files=None):
        data = {self.opts.geom_field: obj.get('geometry')}
        data.update(obj.get('properties'))
        return super(FeatureSerializer, self).from_native(data, files)


class RasterModelSerializer(GeoModelSerializer):
    def get_default_fields(self):
        fields = super(RasterModelSerializer, self).get_default_fields()
        view = self.context.get('view')
        if view and view.request.accepted_renderer.format == 'json':
            try:
                fields[self.opts.raster_field] = NDArrayField()
            except AttributeError:
                pass
        return fields
