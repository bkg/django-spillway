import json
import zipfile

from django import forms
from django.core.files.storage import default_storage
from django.contrib.gis.gdal import OGRGeometry
from django.test import SimpleTestCase, TestCase

from spillway.forms.fields import OGRGeometryField, GeometryFileField
from spillway.collections import Feature
from .models import _geom


class OGRGeometryFieldTestCase(SimpleTestCase):
    def setUp(self):
        self.field = OGRGeometryField()

    def test_feature(self):
        feature = Feature(geometry=_geom)
        geojson = str(feature)
        geom = self.field.to_python(geojson)
        self.assertEqual(json.loads(geom.geojson), feature['geometry'])

    def test_extent(self):
        ex = (0, 0, 10, 10)
        geom = self.field.to_python(','.join(map(str, ex)))
        self.assertEqual(geom.extent, ex)

    def test_invalid(self):
        self.assertRaises(forms.ValidationError, self.field.to_python, '3')


class GeometryFileFieldTestCase(SimpleTestCase):
    def setUp(self):
        self.field = GeometryFileField()
        self.fp = default_storage.open('geofield.json', 'w+b')
        self.fp.write(json.dumps(_geom))
        self.fp.seek(0)

    def test_to_python(self):
        self.assertIsInstance(self.field.to_python(self.fp), OGRGeometry)

    def test_zipfile(self):
        zfile = default_storage.open('geofield.zip', 'w+b')
        with zipfile.ZipFile(zfile, 'w') as zf:
            zf.write(self.fp.name)
        zfile.seek(0)
        self.assertIsInstance(self.field.to_python(zfile), OGRGeometry)
        zfile.close()

    def tearDown(self):
        self.fp.close()
        default_storage.delete(self.fp.name)
