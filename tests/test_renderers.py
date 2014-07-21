import json

from django.contrib.gis.geos import GEOSGeometry
from django.core.paginator import Paginator
from django.test import TestCase
from rest_framework.pagination import PaginationSerializer

from spillway.renderers import GeoJSONRenderer, KMLRenderer
from .models import _geom


class GeoJSONRendererTestCase(TestCase):
    def setUp(self):
        self.data = {'type': 'Feature',
                     'id': 1,
                     'properties': {'name': 'San Francisco'},
                     'geometry': json.dumps(_geom)}
        self.collection = """{
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": %s,
                "id": 1,
                "properties": {"name": "San Francisco"}
            }]
        }""" % json.dumps(_geom)
        self.expected = json.loads(self.collection)
        self.r = GeoJSONRenderer()

    def test_render_dict(self):
        data = json.loads(self.r.render(self.data.copy()))
        geom = json.dumps(data['features'][0]['geometry'])
        # Ensure we can correctly instantiate a GEOS geometry.
        self.assertIsInstance(GEOSGeometry(geom), GEOSGeometry)
        self.assertEqual(geom, self.data['geometry'])
        self.assertEqual(data, self.expected)

    def test_render_list(self):
        data = json.loads(self.r.render([self.data]))
        self.assertEqual(data, self.expected)

    def test_render_paginated(self):
        count = 4
        objects = [self.data.copy() for i in range(count)]
        p = Paginator(objects, 2)
        serializer = PaginationSerializer(p.page(1))
        data = json.loads(self.r.render(serializer.data))
        self.assertEqual(data['count'], count)
        self.assertTrue(*map(data.has_key, ('previous', 'next')))


class KMLRendererTestCase(TestCase):
    def setUp(self):
        self.data = {'id': 1,
                     'properties': {'name': 'playground',
                                    'notes': 'epic slide'},
                     'geometry': GEOSGeometry(json.dumps(_geom)).kml}

    def test_render(self):
        rkml = KMLRenderer()
        resp = rkml.render(self.data)
        self.assertIn(self.data['geometry'], resp.content)
