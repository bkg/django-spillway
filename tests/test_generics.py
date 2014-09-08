import json
import io
import zipfile

from django.core.files import File
from django.test import TestCase
from greenwich.raster import Raster
from rest_framework.test import APIRequestFactory

from spillway import generics
from spillway.renderers import GeoJSONRenderer
from .models import Location, RasterStore
from .test_serializers import RasterStoreTestBase

factory = APIRequestFactory()


class PaginatedGeoListView(generics.GeoListView):
    paginate_by_param = 'page_size'
    paginate_by = 10


class GeoListViewTestCase(TestCase):
    def setUp(self):
        self.view = generics.GeoListView.as_view(model=Location)
        for i in range(20): Location.create()
        self.qs = Location.objects.all()

    def test_list(self):
        request = factory.get('/')
        response = self.view(request)
        self.assertEqual(len(response.data), len(self.qs))

    def test_paginate(self):
        view = PaginatedGeoListView.as_view(model=Location)
        request = factory.get('/', {'page': 2})
        response = view(request).render()
        self.assertEqual(len(response.data['results']),
                         PaginatedGeoListView.paginate_by)

    def test_geojson(self):
        for request in (factory.get('/', {'format': 'geojson'}),
                        factory.get('/', HTTP_ACCEPT=GeoJSONRenderer.media_type)):
            response = self.view(request).render()
            d = json.loads(response.content)
            self.assertEqual(d['features'][0]['geometry'],
                             json.loads(self.qs[0].geom.geojson))


class GeoDetailViewTestCase(TestCase):
    def setUp(self):
        self.view = generics.GeoDetailView.as_view(model=Location)
        for i in range(2): Location.create()
        self.qs = Location.objects.all()

    def test_response(self):
        request = factory.get('/1')
        with self.assertNumQueries(1):
            response = self.view(request, pk=1).render()
        self.assertEqual(response.status_code, 200)
        d = json.loads(response.content)
        self.assertEqual(d['geometry'], json.loads(self.qs[0].geom.geojson))

    def test_kml_response(self):
        request = factory.get('/1', {'format': 'kml'})
        response = self.view(request, pk=1).render()
        self.assertInHTML(self.qs[0].geom.kml, response.content, count=1)


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
        self.assertEquals(*map(len, (d, expected)))
        self.assertDictContainsSubset(expected[0], d[0])

    def test_list_zip(self):
        request = factory.get('/', {'format': 'img.zip'})
        response = self.view(request).render()
        bio = io.BytesIO(response.content)
        zf = zipfile.ZipFile(bio)
        self.assertEqual(len(zf.filelist), len(self.qs))
