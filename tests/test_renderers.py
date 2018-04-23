import sys
import os
import io
import json
import unittest
import zipfile

from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from greenwich import driver_for_path, ImageDriver, Raster
from greenwich.io import MemFileIO

from spillway import carto, forms, renderers
from spillway.collections import Feature, FeatureCollection
from spillway.compat import mapnik
from .models import Location, _geom
from .test_models import RasterTestBase, RasterStoreTestBase
from .test_serializers import RasterStoreSerializer


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
        self.assertIn(self.data['geometry'], zf.read('doc.kml').decode('ascii'))


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


class RasterRendererTestCase(RasterStoreTestBase):
    def _save(self, drivername):
        memio = MemFileIO()
        with self.object.raster() as r:
            r.save(memio, drivername)
        # Mimic a FieldFile.
        memio.path = self.data['image'].path
        return {'image': memio}

    def assert_format(self, data, format):
        memio = MemFileIO()
        memio.write(data)
        r = Raster(memio)
        self.assertEqual(r.driver.format, format)
        r.close()

    def assert_member_formats(self, rend):
        ext = rend.format
        if rend.format.endswith('.zip'):
            ext = os.path.splitext(rend.format)[0]
        pat = 'tmin_.+(?<!\.{0})\.{0}$'.format(ext)
        driver = driver_for_path(ext, ImageDriver.filter_copyable())
        qs = self.qs.warp(format=driver.ext)
        rs = RasterStoreSerializer(qs.zipfiles(), many=True)
        fp = rend.render(rs.data)
        with zipfile.ZipFile(fp) as zf:
            for name in zf.namelist():
                self.assertRegexpMatches(name, pat)
                self.assert_format(zf.read(name), driver.format)
            filecount = len(zf.filelist)
        self.assertEqual(filecount, len(qs))
        fp.close()

    def test_render_geotiff(self):
        fp = renderers.GeoTIFFRenderer().render(self.data)
        self.assertEqual(fp.read(), self.f.read())

    def test_render_hfa(self):
        fp = renderers.HFARenderer().render(self._save('HFA'))
        self.assert_format(fp.read(), 'HFA')

    def test_render_hfazip(self):
        self.assert_member_formats(renderers.HFAZipRenderer())

    def test_render_jpeg(self):
        fp = renderers.JPEGRenderer().render(self._save('JPEG'))
        imgdata = fp.read()
        self.assertEqual(imgdata[:10], b'\xff\xd8\xff\xe0\x00\x10JFIF')
        self.assert_format(imgdata, 'JPEG')

    def test_render_jpegzip(self):
        self.assert_member_formats(renderers.JPEGZipRenderer())

    def test_render_png(self):
        fp = renderers.PNGRenderer().render(self._save('PNG'))
        self.assert_format(fp.read(), 'PNG')

    def test_render_pngzip(self):
        self.assert_member_formats(renderers.PNGZipRenderer())

    def test_render_tifzip(self):
        self.assert_member_formats(renderers.GeoTIFFZipRenderer())


@unittest.skipUnless('mapnik' in sys.modules, 'requires mapnik')
class MapnikRendererTestCase(RasterStoreTestBase):
    ctx = {'y': 51, 'x': 23, 'z': 7}

    def test_compat(self):
        from spillway import compat
        paths = sys.path
        sys.modules.pop('mapnik')
        sys.path = []
        reload(compat)
        with self.assertRaises(ImproperlyConfigured):
            m = compat.mapnik.Map(128, 128)
        sys.path = paths
        reload(compat)

    def test_render(self):
        form = forms.RasterTileForm(self.ctx)
        r = renderers.MapnikRenderer()
        imgdata = carto.build_map([self.object], form).render(r.format)
        im = self._image(r.render(imgdata))
        self.assertEqual(im.size, (256, 256))
        self.assertNotEqual(im.getpixel((100, 100)), (0, 0, 0, 0))

    def test_stylesheet(self):
        m = carto.Map()
        layer = m.layer(self.object, 'green')
        layer._symbolizer.colorizer.default_color = mapnik.Color(0, 255, 0)
        mapnik.save_map(m.map, str(m.mapfile))
        form = forms.RasterTileForm(dict(self.ctx, style='green'))
        r = renderers.MapnikRenderer()
        imgdata = carto.build_map([self.object], form).render(r.format)
        im = self._image(r.render(imgdata))
        self.assertEqual(im.getpixel((100, 100)), (0, 255, 0, 255))
