import json
from io import BytesIO

from django.core.files import File
from rest_framework.test import APIRequestFactory, APITestCase
from PIL import Image

from spillway import views
from .models import Location, RasterStore
from .test_serializers import RasterStoreTestBase


class TileViewTestCase(APITestCase):
    def setUp(self):
        self.geometry = {'type': 'Polygon',
                         'coordinates': [[ [14.14, 50.21],
                                           [14.39, 49.76],
                                           [14.89, 50.20],
                                           [14.14, 50.21] ]]}
        Location.create(name='Prague', geom=self.geometry)

    def test_response(self):
        response = self.client.get('/vectiles/10/553/347/')
        d = json.loads(response.content)
        self.assertNotEqual(d['features'][0]['geometry']['coordinates'],
                            self.geometry['coordinates'])
        # This particular geometry clipped to a tile should have +1 coords.
        self.assertEqual(len(d['features'][0]['geometry']['coordinates'][0]),
                         len(self.geometry['coordinates'][0]) + 1)


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

    def test_empty_tile(self):
        response = self.client.get('/maptiles/1/10/553/347/')
        self.assertEqual(response.status_code, 200)
        self._assert_is_empty_tile(response)

    def test_invalid_tile_coords(self):
        response = self.client.get('/maptiles/1/2/0/100/')
        self.assertEqual(response.status_code, 200)
        self._assert_is_empty_tile(response)
        self._assert_is_empty_tile(self.client.get('/maptiles/1/2/100/100/'))
