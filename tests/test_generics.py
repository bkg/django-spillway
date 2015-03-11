import json
import io
import zipfile

from django.contrib.gis import geos
from django.core.files import File
from django.test import TestCase
from greenwich.raster import Raster
from rest_framework import status
from rest_framework.test import APIRequestFactory

from spillway import generics
from spillway.renderers import GeoJSONRenderer
from .models import Location, RasterStore
from .test_serializers import RasterStoreTestBase, LocationFeatureSerializer

factory = APIRequestFactory()


class PaginatedGeoListView(generics.GeoListView):
    paginate_by_param = 'page_size'
    paginate_by = 10


class GeoDetailViewTestCase(TestCase):
    def setUp(self):
        self.view = generics.GeoDetailView.as_view(model=Location)
        self.radius = 5
        Location.add_buffer((10, -10), self.radius)
        Location.create()
        self.qs = Location.objects.all()

    def test_response(self):
        for params in {}, {'format': 'geojson'}:
            request = factory.get('/1/', params)
            response = None
            with self.assertNumQueries(1):
                response = self.view(request, pk=1).render()
            self.assertEqual(response.status_code, 200)
            feature = json.loads(response.content)
            self.assertEqual(feature['geometry'],
                             json.loads(self.qs[0].geom.geojson))
            self.assertEqual(feature['type'], 'Feature')

    def test_simplify(self):
        request = factory.get('/1/', {'simplify': self.radius})
        response = self.view(request, pk=1).render()
        geom = self.qs[0].geom
        simplified = geos.GEOSGeometry(
            json.dumps(response.data['geometry']), geom.srid)
        self.assertNotEqual(simplified, geom)
        self.assertNotEqual(simplified.num_coords, geom.num_coords)

    def test_kml_response(self):
        request = factory.get('/1/', {'format': 'kml'})
        response = self.view(request, pk=1).render()
        self.assertInHTML(self.qs[0].geom.kml, response.content, count=1)


class GeoListViewTestCase(TestCase):
    def setUp(self):
        self.srid = Location.geom._field.srid
        self.view = generics.GeoListView.as_view(model=Location)
        records = [{'name': 'Banff', 'coordinates': [-115.554, 51.179]},
                   {'name': 'Jasper', 'coordinates': [-118.081, 52.875]}]
        for record in records:
            obj = Location.add_buffer(record.pop('coordinates'), 0.5, **record)
        self.qs = Location.objects.all()

    def _parse_collection(self, response, srid=None):
        data = json.loads(response.content)
        self.assertEqual(data['type'], 'FeatureCollection')
        self.assertEqual(len(data['features']), len(self.qs))
        for feature in data['features']:
            yield geos.GEOSGeometry(
                json.dumps(feature['geometry']), srid or self.srid)

    def test_list(self):
        request = factory.get('/')
        response = self.view(request)
        self.assertEqual(len(response.data['features']), len(self.qs))

    def test_bounding_box(self):
        bbox = self.qs[0].geom.extent
        request = factory.get('/', {'bbox': ','.join(map(str, bbox))})
        response = self.view(request)
        self.assertEqual(len(response.data['features']), 1)

    def test_spatial_lookup(self):
        centroid = Location.objects.centroid()[0].centroid.geojson
        request = factory.get('/', {'intersects': centroid})
        response = self.view(request)
        self.assertEqual(len(response.data['features']), 1)

    def test_spatial_lookup_notfound(self):
        request = factory.get('/', {'intersects': 'POINT(0 0)'})
        response = self.view(request)
        self.assertEqual(len(response.data['features']), 0)

    def test_geojson(self):
        request = factory.get('/', {'format': 'geojson'})
        self.assertIsInstance(self.view(request).accepted_renderer,
                              GeoJSONRenderer)
        request = factory.get('/', HTTP_ACCEPT=GeoJSONRenderer.media_type)
        response = self.view(request).render()
        self.assertIsInstance(response.accepted_renderer, GeoJSONRenderer)
        for geom, obj in zip(self._parse_collection(response), self.qs):
            self.assertTrue(geom.equals_exact(obj.geom, 0.0001))

    def test_simplify(self):
        srid = 3857
        request = factory.get('/', {'simplify': 10000, 'srs': srid,
                                    'format': 'geojson'})
        response = self.view(request).render()
        for geom, obj in zip(self._parse_collection(response, srid), self.qs):
            orig = obj.geom.transform(srid, clone=True)
            self.assertNotEqual(geom, orig)
            self.assertNotEqual(geom.num_coords, orig.num_coords)
        self.assertContains(response, 'EPSG::%d' % srid)


class GeoListCreateAPIView(TestCase):
    def setUp(self):
        self.view = generics.GeoListCreateAPIView.as_view(model=Location)
        Location.create()
        self.qs = Location.objects.all()

    def test_post(self):
        fs = LocationFeatureSerializer(self.qs, many=True)
        request = factory.post('/', fs.data, format='json')
        with self.assertNumQueries(1):
            response = self.view(request).render()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self.qs.get(id=2)
        self.assertEqual(created.name, 'Vancouver')
        self.assertEqual(created.geom, fs.object[0].geom)


class PaginatedGeoListViewTestCase(TestCase):
    def setUp(self):
        self.view = PaginatedGeoListView.as_view(model=Location)
        for i in range(20): Location.create()
        self.qs = Location.objects.all()

    def _test_paginate(self, params, **kwargs):
        request = factory.get('/', params, **kwargs)
        response = self.view(request).render()
        self.assertEqual(len(response.data['features']),
                         PaginatedGeoListView.paginate_by)
        data = json.loads(response.content)
        self.assertEqual(data['count'], len(self.qs))
        self.assertTrue(*map(data.has_key, ('previous', 'next')))
        return data

    def test_paginate(self):
        self._test_paginate({'page': 2})

    def test_paginate_geojson(self):
        data = self._test_paginate(
            {'page': 1}, HTTP_ACCEPT=GeoJSONRenderer.media_type)
        self.assertEqual(data['type'], 'FeatureCollection')


class RasterListViewTestCase(RasterStoreTestBase):
    def setUp(self):
        super(RasterListViewTestCase, self).setUp()
        self.view = generics.RasterListView.as_view(model=RasterStore)

    def test_list_json(self):
        with Raster(self.qs[0].image.path) as r:
            imdata = r.array().tolist()
            g = r.envelope.polygon.__geo_interface__
            sref_wkt = str(r.sref)
        request = factory.get('/')
        response = self.view(request).render()
        d = json.loads(response.content)
        expected = [{'image': imdata, 'geom': g, 'srs': sref_wkt}]
        self.assertEqual(*map(len, (d, expected)))
        self.assertDictContainsSubset(expected[0], d[0])

    def test_list_zip(self):
        request = factory.get('/', {'format': 'img.zip'})
        response = self.view(request)
        self.assertTrue(response.streaming)
        bio = io.BytesIO(''.join(response.streaming_content))
        zf = zipfile.ZipFile(bio)
        self.assertEqual(len(zf.filelist), len(self.qs))
