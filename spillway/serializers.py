from django.core import exceptions
from django.contrib.gis import geos
from django.contrib.gis.db import models
from django.db.models.fields.files import FieldFile
from rest_framework import serializers
from greenwich.srs import SpatialReference

from spillway import query, collections as sc
from spillway.fields import GeometryField
from spillway.renderers.gdal import BaseGDALRenderer

serializers.ModelSerializer.serializer_field_mapping.update({
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
                    break
        return fields


class FeatureListSerializer(serializers.ListSerializer):
    """Feature list serializer for GeoModels."""

    @property
    def data(self):
        return super(serializers.ListSerializer, self).data

    def to_representation(self, data):
        data = map(self.child.to_representation, data)
        try:
            srid = query.get_srid(self.instance)
        except AttributeError:
            srid = None
        return sc.FeatureCollection(features=data, crs=srid)


class FeatureSerializer(GeoModelSerializer):
    """Feature serializer for GeoModels."""

    @classmethod
    def many_init(cls, *args, **kwargs):
        kwargs['child'] = cls()
        meta = getattr(cls, 'Meta', None)
        list_serializer_cls = getattr(
            meta, 'list_serializer_cls', FeatureListSerializer)
        return list_serializer_cls(*args, **kwargs)

    @property
    def data(self):
        if not hasattr(self, '_data'):
            self._data = super(FeatureSerializer, self).data
            if 'crs' not in self._data:
                try:
                    srid = getattr(self.instance, self.Meta.geom_field).srid
                except (AttributeError, geos.GEOSException):
                    pass
                else:
                    self._data['crs'] = sc.NamedCRS(srid)
        return self._data

    def to_representation(self, instance):
        native = super(FeatureSerializer, self).to_representation(instance)
        geometry = native.pop(self.Meta.geom_field)
        pk = native.pop(instance._meta.pk.name, None)
        return sc.Feature(pk, geometry, native)

    def to_internal_value(self, data):
        if sc.has_features(data):
            for feat in data['features']:
                return self.to_internal_value(feat)
        try:
            sref = SpatialReference(data['crs']['properties']['name'])
        except KeyError:
            sref = None
        # Force evaluation of fields property.
        if not self.fields and self.Meta.geom_field is None:
            raise exceptions.FieldDoesNotExist('Geometry field not found')
        record = {self.Meta.geom_field: data.get('geometry')}
        record.update(data.get('properties', {}))
        feature = super(FeatureSerializer, self).to_internal_value(record)
        if feature and sref:
            geom = feature[self.Meta.geom_field]
            geom.srid = sref.srid
        return feature


class RasterModelSerializer(GeoModelSerializer):
    """Serializer class for raster models."""

    def __new__(cls, *args, **kwargs):
        cls.Meta.raster_field = getattr(cls.Meta, 'raster_field', None)
        return super(RasterModelSerializer, cls).__new__(cls, *args, **kwargs)

    def get_fields(self):
        fields = super(RasterModelSerializer, self).get_fields()
        if not self.Meta.raster_field:
            for name, field in fields.items():
                if isinstance(field, serializers.FileField):
                    self.Meta.raster_field = name
                    break
        fieldname = self.Meta.raster_field
        request = self.context.get('request')
        renderer = getattr(request, 'accepted_renderer', None)
        try:
            obj = self.instance[0]
        except (IndexError, TypeError):
            obj = self.instance
        modelfield = getattr(obj, fieldname, None)
        if (isinstance(renderer, BaseGDALRenderer)
                or not isinstance(modelfield, FieldFile)):
            fields[fieldname] = serializers.ReadOnlyField()
        return fields
