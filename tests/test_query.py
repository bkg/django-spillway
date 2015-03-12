from django.test import TestCase
from django.contrib.gis import geos

from spillway.query import GeoQuerySet
from .models import Location


class GeoQuerySetTestCase(TestCase):
    def setUp(self):
        self.radius = 10
        Location.add_buffer((0, 0), self.radius)
        self.qs = Location.objects.all()
        self.srid = 4269

    def test_scale(self):
        sqs = self.qs.scale(0.5, 0.5, format='wkt', precision=2)
        for obj, source in zip(sqs, self.qs):
            geom = geos.GEOSGeometry(obj.wkt)
            self.assertLess(geom.area, source.geom.area)

    def test_simplify(self):
        sqs = self.qs.simplify(self.radius, srid=self.srid, precision=2)
        for obj, source in zip(sqs, self.qs):
            self.assertEqual(obj.geom.srid, self.srid)
            self.assertLess(obj.geom.num_coords, source.geom.num_coords)

    def test_simplify_geojson(self):
        sqs = self.qs.simplify(self.radius, srid=self.srid,
                               format='geojson', precision=2)
        geom = geos.GEOSGeometry(sqs[0].geojson, self.srid)
        source = self.qs[0].geom
        self.assertNotEqual(geom, source)
        self.assertEqual(geom.srid, source.srid)
        self.assertLess(geom.num_coords, source.num_coords)

    def test_simplify_kml(self):
        sqs = self.qs.simplify(self.radius, format='kml')
        self.assertTrue(sqs[0].kml.startswith('<Polygon>'))
        self.assertHTMLNotEqual(sqs[0].kml, self.qs[0].geom.kml)

    def test_extent(self):
        ex = self.qs.extent(3857)
        self.assertEqual(len(ex), 4)
        self.assertLess(ex[0], -180)
