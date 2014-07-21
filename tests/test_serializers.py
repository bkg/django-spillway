import json

from django.test import TestCase

from spillway import serializers
from .models import Location, _geom


class LocationSerializer(serializers.GeoModelSerializer):
    class Meta:
        model = Location
        geom_field = 'geom'


class LocationFeatureSerializer(serializers.FeatureSerializer):
    class Meta:
        model = Location
        geom_field = 'geom'


class ModelTestCase(TestCase):
    def setUp(self):
        self.data = {'id': 1,
                     'name': 'Argentina',
                     'geom': json.dumps(_geom)}
        self.obj = Location(**self.data)
        # GEOSGeometry is not instantiated until save() is called.
        self.obj.save()


class GeoModelSerializerTestCase(ModelTestCase):
    def test_data(self):
        serializer = LocationSerializer(self.data)
        self.assertEqual(serializer.data, self.data)

    def test_restore_object(self):
        serializer = LocationSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.object.name, self.obj.name)
        self.assertEqual(serializer.object.geom, self.obj.geom)
        self.assertEqual(serializer.restore_object(self.data), self.obj)

    def test_list(self):
        data = [self.data.copy() for i in range(3)]
        serializer = LocationSerializer(data)
        self.assertEqual(serializer.data, data)

    def test_get_default_fields(self):
        serializer = LocationSerializer()
        fields = serializer.get_default_fields()
        self.assertEqual(*map(sorted, (self.data, fields)))


class FeatureSerializerTestCase(ModelTestCase):
    def setUp(self):
        super(FeatureSerializerTestCase, self).setUp()
        coords = ()
        for poly in _geom['coordinates']:
            coords += (tuple(map(tuple, poly)),)
        self.expected = {'type': 'Feature',
                         'id': 1,
                         'geometry':  {'type': 'Polygon',
                                       'coordinates': coords},
                         'properties': {'name': 'Argentina'}}

    def test_serialize(self):
        serializer = LocationFeatureSerializer(self.obj)
        self.assertEqual(serializer.data, self.expected)

    def test_deserialize(self):
        serializer = LocationFeatureSerializer(data=self.expected)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.object.geom, self.obj.geom)

        features = [self.expected.copy(), self.expected.copy()]
        serializer = LocationFeatureSerializer(data=features)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.object[0].geom, self.obj.geom)
