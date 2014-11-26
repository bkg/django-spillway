import json

from django import forms
from django.test import SimpleTestCase, TestCase

from spillway.forms.fields import OGRGeometryField
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
