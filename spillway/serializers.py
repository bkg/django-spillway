from django.contrib.gis.db import models
from rest_framework import serializers
from greenwich.srs import SpatialReference

from spillway.collections import (has_features, Feature,
    FeatureCollection, NamedCRS)
from spillway.fields import GeometryField, NDArrayField

serializers.ModelSerializer._field_mapping.mapping.update({
    models.GeometryField: GeometryField,
    models.PointField: GeometryField,
    models.LineStringField: GeometryField,
    models.PolygonField: GeometryField,
    models.MultiPointField: GeometryField,
    models.MultiLineStringField: GeometryField,
    models.MultiPolygonField: GeometryField,
    models.GeometryCollectionField: GeometryField
})


class GeoModelSerializer(serializers.ModelSerializer):
    """Serializer class for GeoModels."""

    def __new__(cls, *args, **kwargs):
        cls.Meta.geom_field = getattr(cls.Meta, 'geom_field', None)
        return super(GeoModelSerializer, cls).__new__(cls, *args, **kwargs)

    def get_fields(self):
        """Returns a fields dict for this serializer with a 'geometry' field
        added.
        """
        fields = super(GeoModelSerializer, self).get_fields()
        # Set the geometry field name when it's undeclared.
        if not self.Meta.geom_field:
            for name, field in fields.items():
                if isinstance(field, GeometryField):
                    self.Meta.geom_field = name
        # Alter geometry field source based on requested format.
        try:
            renderer = self.context['request'].accepted_renderer
        except (AttributeError, KeyError):
            pass
        else:
            geom_field = fields[self.Meta.geom_field]
            if hasattr(self.instance, renderer.format):
                geom_field.source = renderer.format
        return fields


class FeatureListSerializer(serializers.ListSerializer):
    """Feature list serializer for GeoModels."""

    @property
    def data(self):
        return super(serializers.ListSerializer, self).data

    def to_representation(self, data):
        data = super(FeatureListSerializer, self).to_representation(data)
        try:
            srid = (self.instance.query.transformed_srid or
                    self.instance.geo_field.srid)
        except AttributeError:
            srid = None
        return FeatureCollection(features=data, crs=srid)


class FeatureSerializer(GeoModelSerializer):
    """Feature serializer for GeoModels."""

    def __new__(cls, *args, **kwargs):
        cls.Meta.list_serializer_class = getattr(
            cls.Meta, 'list_serializer_class', FeatureListSerializer)
        return super(FeatureSerializer, cls).__new__(cls, *args, **kwargs)

    @property
    def data(self):
        if not hasattr(self, '_data'):
            self._data = super(FeatureSerializer, self).data
            if 'crs' not in self._data:
                geom = getattr(self.instance, self.Meta.geom_field, None)
                if geom and geom.srid:
                    self._data['crs'] = NamedCRS(geom.srid)
        return self._data

    def to_representation(self, instance):
        native = super(FeatureSerializer, self).to_representation(instance)
        geometry = native.pop(self.Meta.geom_field)
        pk = native.pop(instance._meta.pk.name, None)
        return Feature(pk, geometry, native)

    def to_internal_value(self, data):
        if has_features(data):
            for feat in data['features']:
                return self.to_internal_value(feat)
        try:
            sref = SpatialReference(data['crs']['properties']['name'])
        except KeyError:
            sref = None
        if not self.fields and self.Meta.geom_field is None:
            raise Exception('No geometry field found')
        record = {self.Meta.geom_field: data.get('geometry')}
        record.update(data.get('properties', {}))
        feature = super(FeatureSerializer, self).to_internal_value(record)
        if feature and sref:
            geom = feature[self.Meta.geom_field]
            geom.srid = sref.srid
        return feature


class RasterModelSerializer(GeoModelSerializer):
    def __new__(cls, *args, **kwargs):
        cls.Meta.raster_field = getattr(cls.Meta, 'raster_field', None)
        return super(RasterModelSerializer, cls).__new__(cls, *args, **kwargs)

    def get_fields(self):
        fields = super(RasterModelSerializer, self).get_fields()
        if not self.Meta.raster_field:
            for name, field in fields.items():
                if isinstance(field, serializers.FileField):
                    self.Meta.raster_field = name
        request = self.context.get('request')
        render_format = request.accepted_renderer.format if request else None
        # Serialize image data as arrays when json is requested.
        if render_format == 'json':
            fields[self.Meta.raster_field] = NDArrayField()
        elif render_format in ('api', 'html'):
            pass
        elif self.Meta.raster_field and 'path' not in fields:
            # Add a filepath field for GDAL based renderers.
            fields['path'] = serializers.CharField(
                source='%s.path' % self.Meta.raster_field)
        return fields
