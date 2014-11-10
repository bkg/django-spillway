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
        self.wm_srid = 3857

    def test_scale(self):
        sqs = self.qs.scale(0.5, 0.5, format='wkt', precision=2)
        for obj, source in zip(sqs, self.qs):
            geom = GEOSGeometry(obj.wkt)
            self.assertLess(geom.area, source.geom.area)

    def test_simplify(self):
        sqs = self.qs.simplify(0.1, srid=self.wm_srid, precision=2)
        for obj, source in zip(sqs, self.qs):
            self.assertEqual(obj.geom.srid, self.wm_srid)

    def test_simplify_geojson(self):
        sqs = self.qs.simplify(0.1, srid=self.wm_srid, format='geojson', precision=2)
        geom = GEOSGeometry(sqs[0].geojson, self.wm_srid)
        self.assertNotEqual(geom, self.qs[0].geom)
        self.assertEqual(geom.srid, self.qs[0].geom.srid)

    @no_spatialite
    def test_extent(self):
        self.assertEqual(len(self.qs.extent(3857)), 4)
