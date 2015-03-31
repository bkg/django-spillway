from django.test import SimpleTestCase
from rest_framework.routers import DefaultRouter
from rest_framework.test import APIRequestFactory

from spillway.viewsets import GeoModelViewSet
from spillway.renderers import GeoJSONRenderer
from .models import Location
from .test_serializers import LocationFeatureSerializer

factory = APIRequestFactory()


class LocationViewSet(GeoModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationFeatureSerializer


class GeoModelViewSetTestCase(SimpleTestCase):
    def setUp(self):
        self.router = DefaultRouter()
        self.router.register(r'locations', LocationViewSet)
        self.view = LocationViewSet.as_view({'get': 'list'})

    def test_renderer(self):
        request = factory.get('/locations/',
                              HTTP_ACCEPT=GeoJSONRenderer.media_type)
        view = self.view(request)
        self.assertIsInstance(view.accepted_renderer, GeoJSONRenderer)

    def test_register(self):
        self.assertGreater(len(self.router.urls), 0)
