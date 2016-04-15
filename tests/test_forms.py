from django.test import SimpleTestCase
from django.forms import fields
from django.contrib.gis import geos

from spillway import forms


class PKeyQuerySetForm(forms.QuerySetForm):
    pk = fields.IntegerField()


class GeometryQueryFormTestCase(SimpleTestCase):
    def test_data(self):
        form = forms.GeometryQueryForm({'srs': 3857})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['srs'].srid, 3857)


class SpatialQueryFormTestCase(SimpleTestCase):
    def test_data(self):
        data = {'bbox': '-120,38,-118,42'}
        poly = geos.Polygon.from_bbox(data['bbox'].split(','))
        self.expected = {'bboverlaps': poly}
        form = forms.SpatialQueryForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, self.expected)

    def test_intersects(self):
        poly = geos.Polygon.from_bbox((0, 0, 10, 10))
        self.expected = {'intersects': poly}
        data = {'intersects': poly.geojson}
        form = forms.SpatialQueryForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, self.expected)


class QuerySetFormTestCase(SimpleTestCase):
    def test_queryset(self):
        form = PKeyQuerySetForm({'pk': '1'})
        self.assertRaises(TypeError, form.query)
