from django.test import SimpleTestCase

from spillway.collections import Feature


class FeatureTestCase(SimpleTestCase):
    def setUp(self):
        self.crs = {'type': 'name',
                    'properties': {'name': 'urn:ogc:def:crs:EPSG::3310'}}

    def test_crs(self):
        feat = Feature(crs=self.crs)
        self.assertEqual(feat['crs'], self.crs)

    def test_crs_epsg(self):
        self.assertEqual(Feature(crs=3310)['crs'], self.crs)
