import json
from io import BytesIO

from django.core.files import File
from django.contrib.gis import geos
from rest_framework.test import APIRequestFactory, APITestCase
from PIL import Image

from spillway import views
from .models import Location, RasterStore
from .test_serializers import RasterStoreTestBase


class TileViewTestCase(APITestCase):
    def setUp(self):
        self.geometry = {'type': 'Polygon',
                         'coordinates': [[ [14.14, 50.21],
                                           [14.89, 50.20],
                                           [14.39, 49.76],
                                           [14.14, 50.21] ]]}
        Location.create(name='Prague', geom=self.geometry)
        self.g = Location.objects.first().geom
        self.tolerance = .0000001

    def is_polygon_equal(self, d):
        g = geos.Polygon(d['features'][0]['geometry']['coordinates'][0])
        g.srid = self.g.srid
        return g.equals_exact(self.g, self.tolerance)

    def test_clipped_response(self):
        response = self.client.get('/vectiles/10/553/347/?clip=true')
        d = json.loads(response.content)
        self.assertFalse(self.is_polygon_equal(d))
        # This particular geometry clipped to a tile should have +1 coords.
        self.assertEqual(len(d['features'][0]['geometry']['coordinates'][0]),
                         len(self.geometry['coordinates'][0]) + 1)

    def test_unclipped_response(self):
        response = self.client.get('/vectiles/10/553/347.geojson')
        d = json.loads(response.content)
        self.assertTrue(self.is_polygon_equal(d))

    def test_png_response(self):
        response = self.client.get('/vectiles/10/553/347.png')
        self.assertEqual(response['content-type'], 'image/png')
        im = Image.open(BytesIO(response.content))
        self.assertEqual(im.size, (256, 256))


class MapViewTestCase(RasterStoreTestBase, APITestCase):
    def test_response(self):
        response = self.client.get('/maptiles/1/11/342/790/')
        self.assertEqual(response['content-type'], 'image/png')
        im = Image.open(BytesIO(response.content))
        self.assertEqual(im.size, (256, 256))

    def _assert_is_empty_tile(self, response):
        im = Image.open(BytesIO(response.content))
        stats = im.getextrema()
        zero_rgba = ((0, 0), (0, 0), (0, 0), (0, 0))
        self.assertEqual(stats, zero_rgba)

    def test_nonexistent_tileset(self):
        response = self.client.get('/maptiles/999/9/9/9/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_empty_tile(self):
        response = self.client.get('/maptiles/1/10/553/347/')
        self.assertEqual(response.status_code, 200)
        self._assert_is_empty_tile(response)

    def test_invalid_tile_coords(self):
        response = self.client.get('/maptiles/1/2/0/100/')
        self.assertEqual(response.status_code, 200)
        self._assert_is_empty_tile(response)
        self._assert_is_empty_tile(self.client.get('/maptiles/1/2/100/100/'))
