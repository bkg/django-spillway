from django.test import TestCase
from rest_framework import serializers

from spillway import filters
from .models import Location


class FilterTestCase(TestCase):
    def setUp(self):
        self.filter = filters.SpatialLookupFilter()
        Location.create()
        self.queryset = Location.objects.all()

    def test_spatial_lookup(self):
        centroid = self.queryset[0].geom.centroid
        response = self.client.get("/locations/", {"contains": centroid.wkt})
        req = response.renderer_context["request"]
        view = response.renderer_context["view"]
        qcontain = self.filter.filter_queryset(req, self.queryset, view)
        self.assertQuerysetEqual(qcontain, map(repr, self.queryset))

    def test_invalid_value(self):
        response = self.client.get("/locations/", {"contains": 2})
        req = response.renderer_context["request"]
        view = response.renderer_context["view"]
        self.assertRaises(
            serializers.ValidationError,
            self.filter.filter_queryset,
            req,
            self.queryset,
            view,
        )
