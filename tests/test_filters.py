from django.test import TestCase
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from spillway import generics, filters
from .models import Location

factory = APIRequestFactory()


class FilterTestCase(TestCase):
    def setUp(self):
        self.filter = filters.SpatialLookupFilter()
        self.view = generics.GeoListView.as_view(
            queryset=Location.objects.all())
        Location.create()
        self.centroid = Location.objects.centroid()[0].centroid
        self.queryset = Location.objects.all()

    def test_spatial_lookup(self):
        request = factory.get('/', {'contains': self.centroid.wkt})
        ctx = self.view(request).renderer_context
        qcontain = self.filter.filter_queryset(ctx['request'],
                                               self.queryset, self.view)
        self.assertQuerysetEqual(qcontain, map(repr, self.queryset))

    def test_invalid_value(self):
        request = factory.get('/', {'contains': 2})
        ctx = self.view(request).renderer_context
        self.assertRaises(exceptions.ParseError, self.filter.filter_queryset,
                          ctx['request'], self.queryset, self.view)
