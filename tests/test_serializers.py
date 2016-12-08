import json

from django.contrib.gis import geos
from django.test import TestCase
from rest_framework import renderers
from rest_framework.serializers import Serializer
from rest_framework.test import APIRequestFactory
from greenwich.raster import Raster
from greenwich.srs import SpatialReference

from spillway import fields, generics, serializers
from spillway.collections import Feature, FeatureCollection
from spillway.renderers import GeoTIFFRenderer
from .models import Location, RasterStore, _geom
from .test_models import RasterStoreTestBase

factory = APIRequestFactory()


class RequestMock(object):
    def __init__(self):
        self.accepted_renderer = renderers.JSONRenderer()
        self.GET = {}

    def build_absolute_uri(self, url):
        return url


class LocationSerializer(serializers.GeoModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'
        geom_field = 'geom'


class LocationFeatureSerializer(serializers.FeatureSerializer):
    class Meta:
        model = Location
        fields = '__all__'
        geom_field = 'geom'


class RasterStoreSerializer(serializers.RasterModelSerializer):
    class Meta:
        model = RasterStore
        fields = '__all__'


class PaginatedGeoListView(generics.GeoListView):
    queryset = Location.objects.all()
    serializer_class = LocationFeatureSerializer

# Enable pagination for this view
PaginatedGeoListView.pagination_class.page_size = 10


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

    def test_get_fields(self):
        serializer = LocationSerializer()
        fields = serializer.get_fields()
        self.assertEqual(*map(sorted, (self.data, fields)))

    def test_list(self):
        data = [self.data.copy() for i in range(3)]
        serializer = LocationSerializer(data, many=True)
        self.assertEqual(serializer.data, data)

    def test_queryset(self):
        qs = Location.objects.all()
        serializer = LocationSerializer(qs, many=True)
        expected = [self.expected,
                    {'name': 'Vancouver',
                     'id': 2,
                     'geom': self.expected['geom']}]
        self.assertEqual(serializer.data, expected)

    def test_save(self):
        serializer = LocationSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        object = serializer.save()
        self.assertEqual(object.name, self.obj.name)
        self.assertEqual(object.geom, self.obj.geom)

    def test_serialize_object(self):
        serializer = LocationSerializer(self.obj)
        self.assertEqual(serializer.data, self.expected)


class FeatureSerializerTestCase(ModelTestCase):
    def setUp(self):
        super(FeatureSerializerTestCase, self).setUp()
        attrs = {'id': 1,
                 'crs': 4326,
                 'geometry': {'type': 'Polygon',
                              'coordinates': self.coords},
                 'properties': {'name': 'Argentina'}}
        self.expected = Feature(**attrs)

    def test_geometry_field_source(self):
        request = factory.get('/', {'format': 'geojson', 'page': 1})
        response = PaginatedGeoListView.as_view()(request)
        context = {'request': response,
                   'view': response.renderer_context['view']}
        serializer = LocationFeatureSerializer(
            Location.objects.geojson(), many=True, context=context)
        fields = serializer.child.fields
        self.assertEqual(fields['geom'].source, 'geojson')
        # Test serializing paginated objects.
        page = response.renderer_context['view'].paginator.page
        serializer = LocationFeatureSerializer(
            page, many=True, context=context)
        fields = serializer.child.fields
        self.assertEqual(fields['geom'].source, 'geojson')

    def test_serialize(self):
        serializer = LocationFeatureSerializer(self.obj)
        self.assertEqual(serializer.data, self.expected)

    def test_serialize_list(self):
        serializer = LocationFeatureSerializer([self.obj], many=True)
        feat = self.expected.copy()
        feat.pop('crs')
        self.assertEqual(serializer.data, FeatureCollection([feat]))

    def test_serialize_queryset(self):
        serializer = LocationFeatureSerializer(
            Location.objects.all(), many=True)
        feat = self.expected.copy()
        crs = feat.pop('crs')
        self.assertEqual(serializer.data['features'][0], feat)
        self.assertEqual(serializer.data['crs'], crs)

    def test_serialize_queryset_simplify(self):
        # Too high of simplification tolerance should return empty geometry.
        serializer = LocationFeatureSerializer(
            Location.objects.simplify(10, srid=4269)[0])
        self.assertEqual(serializer.data['geometry'], {})

    def test_deserialize(self):
        serializer = LocationFeatureSerializer(data=self.expected)
        self.assertTrue(serializer.is_valid())
        object = serializer.save()
        self.assertEqual(object.geom, self.obj.geom)

    def test_deserialize_projected(self):
        feat = Feature(**dict(self.expected, crs=4269)).copy()
        serializer = LocationFeatureSerializer(data=feat)
        self.assertTrue(serializer.is_valid())
        object = serializer.save()
        self.assertEqual(object.geom.srid, 4269)

    def test_deserialize_list(self):
        features = [self.expected.copy(), self.expected.copy()]
        serializer = LocationFeatureSerializer(data=features, many=True)
        self.assertTrue(serializer.is_valid())
        object = serializer.save()
        self.assertEqual(object[0].geom, self.obj.geom)


class RasterSerializerTestCase(RasterStoreTestBase):
    def setUp(self):
        super(RasterSerializerTestCase, self).setUp()
        self.request = RequestMock()
        self.ctx = {'request': self.request}

    def test_odd_periods(self):
        periods = 3
        qs = self.qs.aggregate_periods(periods)
        serializer = RasterStoreSerializer(qs, many=True, context=self.ctx)
        self.assertEqual(len(serializer.data), len(self.qs))
        self.assertEqual(len(serializer.data[0]['image']), periods)
        self.assertEqual(serializer.data[0]['image'], qs[0].image)

    def test_serialize_queryset(self):
        serializer = RasterStoreSerializer(self.qs, many=True)
        data = serializer.data[0]
        self.assertEqual(data['image'], self.qs[0].image.name)
        expected = {
          'geom': {'type': 'Polygon',
                   'coordinates': (((-120.0, 28.0), (-110.0, 28.0),
                                    (-110.0, 38.0), (-120.0, 38.0), (-120.0, 28.0)),)},
          'minval': 0.0, 'maxval': 24.0, 'nodata': None
        }
        self.assertEqual(SpatialReference(data['srs']), SpatialReference(4326))
        self.assertDictContainsSubset(expected, data)

    def test_serialize_context(self):
        geom = self.object.geom.buffer(-1)
        qs = self.qs.summarize(geom=geom).aggregate_periods(1)
        serializer = RasterStoreSerializer(qs, many=True, context=self.ctx)
        self.assertEqual(len(serializer.data), len(self.qs))
        self.assertEqual(serializer.data[0]['image'], [12.0])
        self.request.accepted_renderer = GeoTIFFRenderer()
        qs = self.qs.warp(format=self.request.accepted_renderer.format,
                          geom=geom)
        serializer = RasterStoreSerializer(qs, many=True, context=self.ctx)
        content = self.f.read()
        self.assertNotEqual(serializer.data[0]['image'].read(), content)

    def test_serialize_bbox(self):
        geom = self.object.geom.buffer(-3)
        qs = self.qs.summarize(geom=geom.envelope)
        serializer = RasterStoreSerializer(qs, many=True, context=self.ctx)
        self.assertEqual(serializer.data[0]['image'].tolist(),
                         [[6, 7, 8], [11, 12, 13], [16, 17, 18]])

    def test_serialize_point_context(self):
        qs = self.qs.summarize(geom=self.object.geom.centroid)
        serializer = RasterStoreSerializer(qs, many=True, context=self.ctx)
        self.assertEqual(len(serializer.data), len(self.qs))
        expected = 12
        self.assertEqual(serializer.data[0]['image'], expected)
        serializer = RasterStoreSerializer(qs[0], context=self.ctx)
        self.assertEqual(serializer.data['image'], expected)
