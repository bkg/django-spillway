from django.test import TestCase
from rest_framework.test import APIRequestFactory

from spillway import generics, filters
from .models import Location

factory = APIRequestFactory()


class FilterTestCase(TestCase):
    def setUp(self):
        self.view = generics.GeoListView.as_view(model=Location)
        Location.create()
        self.centroid = Location.objects.centroid()[0].centroid

    def test_spatial_lookup(self):
        request = factory.get('/', {'contains': self.centroid.wkt})
        ctx = self.view(request).renderer_context
        queryset = Location.objects.all()
        spfilt = filters.SpatialLookupFilter()
        qcontain = spfilt.filter_queryset(ctx['request'], queryset, self.view)
        self.assertQuerysetEqual(qcontain, map(repr, queryset))
