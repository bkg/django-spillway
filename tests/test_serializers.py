import json
import tempfile

from django.core.files import File
from django.core.files.storage import default_storage
from django.test import SimpleTestCase, TestCase
from rest_framework.serializers import Serializer, ModelSerializer
from PIL import Image
from greenwich.raster import Raster, frombytes

from spillway import serializers, fields
from .models import Location, RasterStore, _geom

# Store tempfiles in the temp media root.
tempfile.tempdir = default_storage.location

def create_image():
    fp = tempfile.NamedTemporaryFile(suffix='.tif')
    ras = frombytes(bytes(bytearray(range(25))), (5, 5))
    ras.affine = (-120, 2, 0, 38, 0, -2)
    ras.sref = 4326
    ras.save(fp)
    ras.close()
    fp.seek(0)
    return fp


class LocationSerializer(serializers.GeoModelSerializer):
    class Meta:
        model = Location
        geom_field = 'geom'


class LocationFeatureSerializer(serializers.FeatureSerializer):
    class Meta:
        model = Location
        geom_field = 'geom'


class ArraySerializer(Serializer):
    path = fields.NDArrayField()


class RasterStoreSerializer(serializers.RasterModelSerializer):
    #image = fields.NDArrayField()

    class Meta:
        model = RasterStore


class GDALModelSerializer(serializers.RasterModelSerializer):
    image = fields.GDALField()

    class Meta:
        model = RasterStore


class RasterTestBase(SimpleTestCase):
    def setUp(self):
        self.f = create_image()
        self.data = {'path': self.f.name}

    def tearDown(self):
        self.f.close()


class ModelTestCase(TestCase):
    def setUp(self):
        self.data = {'id': 1,
                     'name': 'Argentina',
                     'geom': json.dumps(_geom)}
        self.obj = Location(**self.data)
        # GEOSGeometry is not instantiated until save() is called.
        self.obj.save()
        Location.create()
        self.coords = ()
        for poly in _geom['coordinates']:
            self.coords += (tuple(map(tuple, poly)),)
        self.expected = {'id': 1,
                         'name': 'Argentina',
                         'geom': {'type': 'Polygon',
                                  'coordinates': self.coords}}


class GeoModelSerializerTestCase(ModelTestCase):
    def test_data(self):
        serializer = LocationSerializer(self.data)
        self.assertEqual(serializer.data, self.data)

    def test_get_default_fields(self):
        serializer = LocationSerializer()
        fields = serializer.get_default_fields()
        self.assertEqual(*map(sorted, (self.data, fields)))

    def test_list(self):
        data = [self.data.copy() for i in range(3)]
        serializer = LocationSerializer(data)
        self.assertEqual(serializer.data, data)

    def test_queryset(self):
        qs = Location.objects.all()
        serializer = LocationSerializer(qs)
        expected = [self.expected,
                    {'name': 'Vancouver',
                     'id': 2,
                     'geom': self.expected['geom']}]
        self.assertEqual(serializer.data, expected)

    def test_restore_object(self):
        serializer = LocationSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.object.name, self.obj.name)
        self.assertEqual(serializer.object.geom, self.obj.geom)
        self.assertEqual(serializer.restore_object(self.data), self.obj)

    def test_serialize_object(self):
        serializer = LocationSerializer(self.obj)
        self.assertEqual(serializer.data, self.expected)


class FeatureSerializerTestCase(ModelTestCase):
    def setUp(self):
        super(FeatureSerializerTestCase, self).setUp()
        self.expected = {'type': 'Feature',
                         'id': 1,
                         'geometry': {'type': 'Polygon',
                                      'coordinates': self.coords},
                         'properties': {'name': 'Argentina'}}

    def test_serialize(self):
        serializer = LocationFeatureSerializer(self.obj)
        self.assertEqual(serializer.data, self.expected)
        serializer = LocationFeatureSerializer([self.obj])
        self.assertEqual(serializer.data, [self.expected])

    def test_deserialize(self):
        serializer = LocationFeatureSerializer(data=self.expected)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.object.geom, self.obj.geom)

        features = [self.expected.copy(), self.expected.copy()]
        serializer = LocationFeatureSerializer(data=features)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.object[0].geom, self.obj.geom)

    def test_feature(self):
        exp = self.expected.copy()
        exp.pop('type')
        feat = serializers.Feature(**exp)
        self.assertJSONEqual(str(feat), json.dumps(self.expected))
        # Test handling of pre-serialized geometry
        exp['geometry'] = json.dumps(exp['geometry'])
        feat = serializers.Feature(**exp)
        self.assertJSONEqual(str(feat), json.dumps(self.expected))


class RasterSerializerTestCase(RasterTestBase):
    def test_array_serializer(self):
        serializer = ArraySerializer(self.data)
        arr = serializer.data['path']
        self.assertEqual(arr, Raster(self.data['path']).array().tolist())
