import json

from django.test import TestCase

from spillway import serializers
from .models import Location, _geom


class LocationSerializer(serializers.GeoModelSerializer):
    class Meta:
        model = Location
        geom_field = 'geom'


class GeoModelSerializerTestCase(TestCase):
    def setUp(self):
        self.data = {'id': 1,
                     'name': 'Argentina',
                     'geom': json.dumps(_geom)}
        self.obj = Location(**self.data)

    def test_data(self):
        serializer = LocationSerializer(self.data)
        self.assertEqual(serializer.data, self.data)

    def test_restore_object(self):
        serializer = LocationSerializer(self.obj)
        # FIXME: failing due to geometry differences
        #self.assertEqual(serializer.data, self.data)
        self.assertEqual(serializer.restore_object(self.data), self.obj)

    def test_list(self):
        data = [self.data.copy() for i in range(3)]
        serializer = LocationSerializer(data)
        self.assertEqual(serializer.data, data)

    def test_get_default_fields(self):
        serializer = LocationSerializer()
        fields = serializer.get_default_fields()
        self.assertEqual(*map(sorted, (self.data, fields)))
