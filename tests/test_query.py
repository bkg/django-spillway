from django.test import TestCase
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.tests.utils import no_spatialite

from spillway.query import GeoQuerySet
from .models import Location


class GeoQuerySetTestCase(TestCase):
    def setUp(self):
        for i in range(3):
            obj = Location.create()
        self.qs = Location.objects.all()

    def test_scale(self):
        sqs = self.qs.scale(0.5, 0.5, format='wkt', precision=2)
        for obj, source in zip(sqs, self.qs):
            geom = GEOSGeometry(obj.wkt)
            self.assertLess(geom.area, source.geom.area)

    def test_simplify(self):
        # Sets a wkb buffer for 'geom'
        sqs = self.qs.simplify(0.1, srid=3857, precision=2)
        for obj, source in zip(sqs, self.qs):
            #self.assertEqual(obj.geom.srid, 3857)
            self.assertIsInstance(obj.geom, GEOSGeometry)

    def test_simplify_geojson(self):
        srid = 3857
        sqs = self.qs.simplify(0.1, srid=srid, format='geojson', precision=2)
        geom = GEOSGeometry(sqs[0].geojson, srid)
        self.assertNotEqual(geom, self.qs[0].geom)
        self.assertIsNotNone(geom.srid)
        self.assertNotEqual(geom.srid, self.qs[0].geom.srid)

    @no_spatialite
    def test_extent(self):
        self.assertEqual(len(self.qs.extent(3857)), 4)
