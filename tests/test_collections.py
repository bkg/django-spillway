import datetime

from django.test import SimpleTestCase
from spillway.collections import Feature, LinkedCRS, NamedCRS


class FeatureTestCase(SimpleTestCase):
    def setUp(self):
        self.crs = {'type': 'name',
                    'properties': {'name': 'urn:ogc:def:crs:EPSG::3310'}}

    def test_crs(self):
        feat = Feature(crs=self.crs)
        self.assertEqual(feat['crs'], self.crs)

    def test_crs_epsg(self):
        self.assertEqual(Feature(crs=3310)['crs'], self.crs)

    def test_crs_dict(self):
        self.assertEqual(NamedCRS(self.crs), self.crs)
        self.assertEqual(NamedCRS(**self.crs), self.crs)

    def test_empty_crs(self):
        crs = {'type': 'name',
               'properties': {'name': 'urn:ogc:def:crs:EPSG::4326'}}
        self.assertEqual(NamedCRS(), crs)

    def test_str(self):
        feat = Feature(properties={'event': datetime.date(1899, 1, 1)})
        self.assertIn('"properties": {"event": "1899-01-01"}}', str(feat))


class LinkedCRSTestCase(SimpleTestCase):
    def setUp(self):
        self.crs = {
            'type': 'link',
            'properties': {
                'href': 'http://spatialreference.org/ref/epsg/4269/proj4/',
                'type': 'proj4'
            }
        }

    def test_srid(self):
        self.assertEqual(LinkedCRS(4269), self.crs)
        self.assertEqual(LinkedCRS(srid=4269), self.crs)

    def test_dict(self):
        self.assertEqual(LinkedCRS(properties=self.crs['properties']), self.crs)
        self.assertEqual(LinkedCRS(self.crs), self.crs)
        self.assertEqual(LinkedCRS(**self.crs), self.crs)
