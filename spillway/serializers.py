from django.contrib.gis.db import models
from rest_framework import serializers, pagination
from greenwich.srs import SpatialReference

from spillway.collections import Feature, FeatureCollection, NamedCRS
from spillway.fields import GeometryField, NDArrayField


class GeoModelSerializerOptions(serializers.ModelSerializerOptions):
    def __init__(self, meta):
        super(GeoModelSerializerOptions, self).__init__(meta)
        self.geom_field = getattr(meta, 'geom_field', None)


class GeoModelSerializer(serializers.ModelSerializer):
    """Serializer class for GeoModels."""
    _options_class = GeoModelSerializerOptions
    field_mapping = dict({
        models.GeometryField: GeometryField,
        models.PointField: GeometryField,
        models.LineStringField: GeometryField,
        models.PolygonField: GeometryField,
        models.MultiPointField: GeometryField,
        models.MultiLineStringField: GeometryField,
        models.MultiPolygonField: GeometryField,
        models.GeometryCollectionField: GeometryField
    }, **serializers.ModelSerializer.field_mapping)

    def get_default_fields(self):
        """Returns a fields dict for this serializer with a 'geometry' field
        added.
        """
        fields = super(GeoModelSerializer, self).get_default_fields()
        # Set the geometry field name when it's undeclared.
        if not self.opts.geom_field:
            for name, field in fields.items():
                if isinstance(field, GeometryField):
                    self.opts.geom_field = name
        return fields


class FeatureSerializer(GeoModelSerializer):
    def __init__(self, *args, **kwargs):
        super(FeatureSerializer, self).__init__(*args, **kwargs)
        self.fields[self.opts.geom_field].set_default_source()

    @property
    def data(self):
        if self._data is None:
            data = super(FeatureSerializer, self).data
            fieldname = self.opts.geom_field
            if self.many or isinstance(data, (list, tuple)):
                try:
                    srid = (self.object.query.transformed_srid or
                            self.object.geo_field.srid)
                except AttributeError:
                    srid = None
                self._data = FeatureCollection(features=data, crs=srid)
            else:
                try:
                    geom = getattr(self.object, fieldname)
                except AttributeError:
                    pass
                else:
                    self._data['crs'] = NamedCRS(geom.srid)
        return self._data

    def to_native(self, obj):
        native = super(FeatureSerializer, self).to_native(obj)
        geometry = native.pop(self.opts.geom_field)
        pk = native.pop(obj._meta.pk.name, None)
        return Feature(pk, geometry, native)

    def from_native(self, data, files=None):
        if data and 'features' in data:
            for feat in data['features']:
                return self.from_native(feat, files)
        try:
            sref = SpatialReference(data['crs']['properties']['name'])
        except KeyError:
            sref = None
        record = {self.opts.geom_field: data.get('geometry')}
        record.update(data.get('properties', {}))
        feature = super(FeatureSerializer, self).from_native(record, files)
        if feature and sref:
            geom = getattr(feature, self.opts.geom_field)
            geom.srid = sref.srid
        return feature


class PaginatedFeatureSerializer(pagination.PaginationSerializer):
    results_field = 'features'


class RasterModelSerializerOptions(GeoModelSerializerOptions):
    def __init__(self, meta):
        super(RasterModelSerializerOptions, self).__init__(meta)
        self.raster_field = getattr(meta, 'raster_field', None)


class RasterModelSerializer(GeoModelSerializer):
    _options_class = RasterModelSerializerOptions

    def get_default_fields(self):
        fields = super(RasterModelSerializer, self).get_default_fields()
        if not self.opts.raster_field:
            for name, field in fields.items():
                if isinstance(field, serializers.FileField):
                    self.opts.raster_field = name
        request = self.context.get('request')
        render_format = request.accepted_renderer.format if request else None
        # Serialize image data as arrays when json is requested.
        if render_format == 'json':
            fields[self.opts.raster_field] = NDArrayField()
        elif render_format in ('api', 'html'):
            pass
        elif self.opts.raster_field and 'path' not in fields:
            # Add a filepath field for GDAL based renderers.
            fields['path'] = serializers.CharField(
                source='%s.path' % self.opts.raster_field)
        return fields
