from django.test import TestCase
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory

from spillway import generics
from .models import Location

factory = APIRequestFactory()


class PaginatedGeoListView(generics.GeoListView):
    paginate_by_param = 'page_size'
    paginate_by = 10


class GeoListViewTestCase(TestCase):
    def setUp(self):
        self.view = generics.GeoListView.as_view(model=Location)
        for i in range(20): Location.create()
        self.qs = Location.objects.all()

    def test_list(self):
        request = factory.get('/')
        response = self.view(request)
        self.assertEqual(len(response.data), len(self.qs))

    def test_paginate(self):
        view = PaginatedGeoListView.as_view(model=Location)
        request = factory.get('/', {'page': 2})
        response = view(request)
        self.assertEqual(len(response.data['results']),
                         PaginatedGeoListView.paginate_by)
