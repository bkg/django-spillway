import io
import json
import zipfile

from django.contrib.gis.geos import GEOSGeometry
from django.core.paginator import Paginator
from django.test import SimpleTestCase, TestCase
from rest_framework.pagination import PaginationSerializer
from PIL import Image

from spillway import renderers
from .models import Location, _geom
from .test_serializers import RasterTestBase, RasterStoreTestBase


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
        self.r = renderers.GeoJSONRenderer()

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
        rkml = renderers.KMLRenderer()
        self.assertIn(self.data['geometry'], rkml.render(self.data))

    def test_render_kmz(self):
        rkmz = renderers.KMZRenderer()
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
        rsvg = renderers.SVGRenderer()
        svgdoc = rsvg.render(self.data)
        self.assertIn(self.data['geometry'], svgdoc)

        #serializer = FeatureSerializer(self.qs)
        ##serializer.opts.model = self.qs.model
        #svgdoc = rsvg.render(serializer.data)
        #print svgdoc
        #self.assertIn(self.data['geometry'], svgdoc)


class RasterRendererTestCase(RasterTestBase):
    img_header = 'EHFA_HEADER_TAG'

    def test_render_geotiff(self):
        f = renderers.GeoTIFFRenderer().render(self.data)
        self.assertEqual(f.filelike.read(), self.f.read())

    def test_render_imagine(self):
        data = renderers.HFARenderer().render(self.data)
        # Read the image header.
        self.assertEqual(data.filelike[:15], self.img_header)

    def test_render_hfazip(self):
        f = renderers.HFAZipRenderer().render(self.data)
        zf = zipfile.ZipFile(f.filelike)
        self.assertTrue(all(name.endswith('.img') for name in zf.namelist()))
        self.assertEqual(zf.read(zf.namelist()[0])[:15], self.img_header)

    def test_render_tifzip(self):
        tifs = [self.data, self.data]
        f = renderers.GeoTIFFZipRenderer().render(tifs)
        zf = zipfile.ZipFile(f.filelike)
        self.assertEqual(len(zf.filelist), len(tifs))
        self.assertTrue(all(name.endswith('.tif') for name in zf.namelist()))


class MapnikRendererTestCase(RasterStoreTestBase):
    def test_render(self):
        ctx = {'bbox': self.object.geom}
        imgdata = renderers.MapnikRenderer().render(
            self.object, renderer_context=ctx)
        im = Image.open(io.BytesIO(imgdata))
        self.assertEqual(im.size, (256, 256))
        self.assertNotEqual(im.getpixel((100, 100)), (0, 0, 0, 0))
