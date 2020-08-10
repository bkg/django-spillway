from io import BytesIO
import unittest

from django.core.exceptions import ImproperlyConfigured
from django.core.files import File
from django.contrib.gis import geos
from rest_framework.test import APIRequestFactory, APITestCase
from PIL import Image

from spillway import urls, views
from spillway.compat import mapnik
from .models import Location
from .test_models import RasterStoreTestBase

try:
    has_mapnik = bool(mapnik.Map)
except ImproperlyConfigured:
    has_mapnik = False


class TileViewTestCase(APITestCase):
    def setUp(self):
        self.geometry = {
            "type": "Polygon",
            "coordinates": [
                [[14.14, 50.21], [14.89, 50.20], [14.39, 49.76], [14.14, 50.21]]
            ],
        }
        Location.create(name="Prague", geom=self.geometry)
        self.g = Location.objects.first().geom
        self.tolerance = 0.0000001
        self.url = "/vectiles/10/553/347"

    def is_polygon_equal(self, d):
        g = geos.Polygon(d["features"][0]["geometry"]["coordinates"][0])
        g.srid = self.g.srid
        return g.equals_exact(self.g, self.tolerance)

    def test_clipped_response(self):
        response = self.client.get("%s/?clip=true" % self.url)
        d = response.json()
        self.assertFalse(self.is_polygon_equal(d))
        # This particular geometry clipped to a tile should have +1 coords.
        self.assertEqual(
            len(d["features"][0]["geometry"]["coordinates"][0]),
            len(self.geometry["coordinates"][0]) + 1,
        )

    def test_unclipped_response(self):
        response = self.client.get("%s.geojson" % self.url)
        self.assertTrue(self.is_polygon_equal(response.json()))

    @unittest.skipUnless(has_mapnik, "requires mapnik")
    def test_png_response(self):
        response = self.client.get("%s.png" % self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "image/png")
        im = Image.open(BytesIO(response.content))
        self.assertEqual(im.size, (256, 256))

    @unittest.skipUnless(has_mapnik, "requires mapnik")
    def test_tile_outside_extent(self):
        response = self.client.get("/vectiles/4/7/8.png")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["content-type"], "text/html")

    def test_is_tilepath(self):
        self.assertTrue(urls.is_tilepath(self.url))
        self.assertTrue(urls.is_tilepath("%s.png" % self.url))
        self.assertFalse(urls.is_tilepath("/blog/2010/03/"))


class RasterTileViewTestCase(RasterStoreTestBase, APITestCase):
    @unittest.skipUnless(has_mapnik, "requires mapnik")
    def test_response(self):
        response = self.client.get("/maptiles/1/11/342/790/")
        self.assertEqual(response["content-type"], "image/png")
        im = Image.open(BytesIO(response.content))
        self.assertEqual(im.size, (256, 256))
        stats = im.getextrema()
        zero_rgba = ((0, 0), (0, 0), (0, 0), (0, 0))
        self.assertEqual(stats, zero_rgba)

    def test_nonexistent_tileset(self):
        response = self.client.get("/maptiles/999/9/9/9/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["content-type"], "application/json")

    def test_nonexistent_tileset_format(self):
        response = self.client.get("/maptiles/999/9/9/9.png")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["content-type"], "text/html")

    @unittest.skipUnless(has_mapnik, "requires mapnik")
    def test_invalid_tile_coords(self):
        response = self.client.get("/maptiles/1/2/0/100/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["content-type"], "application/json")

    @unittest.skipUnless(has_mapnik, "requires mapnik")
    def test_tile_outside_extent(self):
        response = self.client.get("/maptiles/1/5/16/10.png")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["content-type"], "text/html")
