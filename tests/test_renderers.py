import io
import json
import zipfile

from django.contrib.gis.geos import GEOSGeometry
from django.core.paginator import Paginator
from django.test import SimpleTestCase, TestCase
from rest_framework.pagination import PaginationSerializer

from spillway.renderers import (GeoJSONRenderer, KMLRenderer,
    KMZRenderer, SVGRenderer, GeoTIFFRenderer, GeoTIFFZipRenderer, HFARenderer, HFAZipRenderer)
from spillway.serializers import FeatureSerializer
from .models import Location, _geom
from .test_serializers import RasterTestBase


class GeoJSONRendererTestCase(SimpleTestCase):
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
        self.empty = '{"type": "FeatureCollection", "features": []}'
        self.r = GeoJSONRenderer()

    def test_render_dict(self):
        data = json.loads(self.r.render(self.data.copy()))
        geom = json.dumps(data['features'][0]['geometry'])
        # Ensure we can correctly instantiate a GEOS geometry.
        self.assertIsInstance(GEOSGeometry(geom), GEOSGeometry)
        self.assertEqual(geom, self.data['geometry'])
        self.assertEqual(data, self.expected)
        self.assertEqual(self.r.render({}), self.empty)

    def test_render_list(self):
        data = json.loads(self.r.render([self.data]))
        self.assertEqual(data, self.expected)
        self.assertEqual(self.r.render([]), self.empty)

    def test_render_paginated(self):
        count = 4
        objects = [self.data.copy() for i in range(count)]
        p = Paginator(objects, 2)
        serializer = PaginationSerializer(p.page(1))
        data = json.loads(self.r.render(serializer.data))
        self.assertEqual(data['count'], count)
        self.assertTrue(*map(data.has_key, ('previous', 'next')))


class KMLRendererTestCase(SimpleTestCase):
    def setUp(self):
        self.data = {'id': 1,
                     'properties': {'name': 'playground',
                                    'notes': 'epic slide'},
                     'geometry': GEOSGeometry(json.dumps(_geom)).kml}

    def test_render(self):
        rkml = KMLRenderer()
        self.assertIn(self.data['geometry'], rkml.render(self.data))

    def test_render_kmz(self):
        rkmz = KMZRenderer()
        stream = io.BytesIO(rkmz.render(self.data))
        self.assertTrue(zipfile.is_zipfile(stream))
        zf = zipfile.ZipFile(stream)
        self.assertIn(self.data['geometry'], zf.read('doc.kml'))


class SVGRendererTestCase(TestCase):
    def setUp(self):
        Location.create()
        self.qs = Location.objects.svg()
        self.svg = self.qs[0].svg
        self.data = {'id': 1,
                     'properties': {'name': 'playground',
                                    'notes': 'epic slide'},
                     'geometry': self.svg}

    def test_render(self):
        rsvg = SVGRenderer()
        svgdoc = rsvg.render(self.data)
        self.assertIn(self.data['geometry'], svgdoc)


class RasterRendererTestCase(RasterTestBase):
    def test_render_geotiff(self):
        f = GeoTIFFRenderer().render(self.data)
        self.assertEqual(f.filelike.read(), self.f.read())

    def test_render_imagine(self):
        data = HFARenderer().render(self.data)
        img_header = 'EHFA_HEADER_TAG'
        # Read the image header.
        self.assertEqual(data.filelike[:15], img_header)

    def test_render_hfazip(self):
        data = HFAZipRenderer().render(self.data)
        #data = HFAZipRenderer().render([self.data])
        self.assertTrue(zipfile.is_zipfile(data.filelike))

    def test_render_tifzip(self):
        f = GeoTIFFZipRenderer().render([self.data, self.data])
        #self.assertEqual(f.filelike.read(), self.f.read())
        self.assertTrue(zipfile.is_zipfile(f.filelike))
