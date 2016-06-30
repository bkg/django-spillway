import sys
import os
import io
import json
import unittest
import zipfile

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from greenwich import Raster
from greenwich.io import MemFileIO

from spillway import carto, forms, renderers
from spillway.collections import Feature, FeatureCollection
from .models import Location, _geom
from .test_models import RasterTestBase, RasterStoreTestBase


class GeoJSONRendererTestCase(SimpleTestCase):
    def setUp(self):
        self.data = Feature(id=1, properties={'name': 'San Francisco'},
                            geometry=_geom)
        self.collection = FeatureCollection(features=[self.data])
        self.r = renderers.GeoJSONRenderer()

    def test_render_feature(self):
        data = json.loads(self.r.render(self.data))
        self.assertEqual(data, self.data)
        self.assertEqual(self.r.render({}), str(Feature()))

    def test_render_feature_collection(self):
        data = json.loads(self.r.render(self.collection))
        self.assertEqual(data, self.collection)
        self.assertEqual(self.r.render([]), str(FeatureCollection()))

    def test_render_list(self):
        data = json.loads(self.r.render([self.data]))
        self.assertEqual(data, self.collection)


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

    def _save(self, drivername):
        memio = MemFileIO()
        with Raster(self.data['image'].path) as r:
            r.save(memio, drivername)
        # Mimic a FieldFile.
        memio.path = self.data['image'].path
        return {'image': memio}

    def assert_format(self, data, format):
        im = self._image(data)
        self.assertEqual(im.format, format)

    def assert_member_formats(self, obj, format):
        imgs = [self._save(format)]
        fp = obj.render(imgs)
        with zipfile.ZipFile(fp) as zf:
            for name in zf.namelist():
                self.assert_format(zf.read(name), format)
            filecount = len(zf.filelist)
        self.assertEqual(filecount, len(imgs))
        fp.close()

    def test_render_csv(self):
        fp = renderers.CSVRenderer().render(self._save('XYZ'))
        self.assertEqual(fp.readline(), 'X,Y,Z\n')

    def test_render_geotiff(self):
        fp = renderers.GeoTIFFRenderer().render(self.data)
        self.assertEqual(fp.read(), self.f.read())

    def test_render_hfa(self):
        fp = renderers.HFARenderer().render(self._save('HFA'))
        # Read the image header.
        self.assertEqual(fp.read()[:15], self.img_header)

    def test_render_hfazip(self):
        fp = renderers.HFAZipRenderer().render(self._save('HFA'))
        zf = zipfile.ZipFile(fp)
        for name in zf.namelist():
            self.assertRegexpMatches(name, '(?<!\.img)\.img$')
        self.assertEqual(zf.read(zf.namelist()[0])[:15], self.img_header)

    def test_render_jpeg(self):
        fp = renderers.JPEGRenderer().render(self._save('JPEG'))
        imgdata = fp.read()
        self.assertEqual(imgdata[:10], '\xff\xd8\xff\xe0\x00\x10JFIF')

    @unittest.skipIf('TRAVIS' in os.environ,
                     'known issue when reading jpegs with Pillow on '
                     'Travis build enviroment')
    def test_render_jpegzip(self):
        self.assert_member_formats(renderers.JPEGZipRenderer(), 'JPEG')

    def test_render_png(self):
        fp = renderers.PNGRenderer().render(self._save('PNG'))
        self.assert_format(fp.read(), 'PNG')

    def test_render_pngzip(self):
        self.assert_member_formats(renderers.PNGZipRenderer(), 'PNG')

    def test_render_tifzip(self):
        tifs = [self.data]
        fp = renderers.GeoTIFFZipRenderer().render(tifs)
        zf = zipfile.ZipFile(fp)
        self.assertEqual(len(zf.filelist), len(tifs))
        self.assertTrue(all(name.endswith('.tif') for name in zf.namelist()))


class MapnikRendererTestCase(RasterStoreTestBase):
    def test_render(self):
        ctx = {'y': 51, 'x': 23, 'z': 7}
        form = forms.RasterTileForm(ctx)
        r = renderers.MapnikRenderer()
        imgdata = carto.build_map([self.object], form).render(r.format)
        im = self._image(r.render(imgdata))
        self.assertEqual(im.size, (256, 256))
        self.assertNotEqual(im.getpixel((100, 100)), (0, 0, 0, 0))

    def test_compat(self):
        from spillway import compat
        sys.modules.pop('mapnik')
        sys.path = []
        reload(compat)
        with self.assertRaises(ImproperlyConfigured):
            m = compat.mapnik.Map(128, 128)
