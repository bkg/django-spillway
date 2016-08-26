import datetime

from django.test import SimpleTestCase
from spillway.collections import (Feature, FeatureCollection, LayerCollection,
    LinkedCRS, NamedCRS, as_feature)


class FeatureTestCase(SimpleTestCase):
    def setUp(self):
        self.crs = {'type': 'name',
                    'properties': {'name': 'urn:ogc:def:crs:EPSG::3310'}}
        self.geom = {'type': 'Point', 'coordinates': [0, 0]}

    def test_copy(self):
        self.assertIsInstance(Feature().copy(), Feature)

    def test_crs(self):
        feat = Feature(crs=self.crs)
        self.assertEqual(feat['crs'], self.crs)

    def test_crs_epsg(self):
        self.assertEqual(Feature(crs=3310)['crs'], self.crs)

    def test_crs_dict(self):
        self.assertEqual(NamedCRS(self.crs), self.crs)
        self.assertEqual(NamedCRS(**self.crs), self.crs)

    def test_dict(self):
        self.assertEqual(Feature(**{'geometry': self.geom, 'name': 'atlantic'}),
                         {'geometry': self.geom, 'type': 'Feature',
                          'properties': {'name': 'atlantic'}})

    def test_empty_crs(self):
        crs = {'type': 'name',
               'properties': {'name': 'urn:ogc:def:crs:EPSG::4326'}}
        self.assertEqual(NamedCRS(), crs)

    def test_iterable(self):
        iterable = (('geometry', self.geom),)
        self.assertEqual(Feature(iterable=iterable),
                         {'geometry': self.geom, 'type': 'Feature', 'properties': {}})

    def test_str(self):
        feat = Feature(properties={'event': datetime.date(1899, 1, 1)})
        self.assertIn('"properties": {"event": "1899-01-01"}}', str(feat))


class LayerCollectionTestCase(SimpleTestCase):
    def setUp(self):
        # Instantiate using a plain dict as we want to test for conversion to a
        # layer FeatureCollection below.
        self.lc = LayerCollection({'layer': dict(**FeatureCollection())})

    def test_has_featurecollection(self):
        self.assertIsInstance(self.lc['layer'], FeatureCollection)

    def test_geojson(self):
        self.assertIn('{"layer":', self.lc.geojson)

    def test_as_feature(self):
        self.assertIsInstance(as_feature(dict(self.lc['layer'])),
                              FeatureCollection)
        self.assertIsInstance(as_feature(dict(self.lc)), LayerCollection)


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
