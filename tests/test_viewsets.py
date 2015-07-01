from django.test import SimpleTestCase
from rest_framework.routers import DefaultRouter
from rest_framework.test import APIRequestFactory

from spillway import viewsets
from spillway.renderers import GeoJSONRenderer, GeoTIFFZipRenderer
from .models import Location, RasterStore
from .test_serializers import LocationFeatureSerializer, RasterStoreSerializer

factory = APIRequestFactory()


class LocationViewSet(viewsets.GeoModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationFeatureSerializer


class RasterViewSet(viewsets.ReadOnlyRasterModelViewSet):
    queryset = RasterStore.objects.all()
    serializer_class = RasterStoreSerializer


class GeoModelViewSetTestCase(SimpleTestCase):
    def setUp(self):
        self.router = DefaultRouter()
        self.router.register(r'locations', LocationViewSet)
        self.view = LocationViewSet.as_view({'get': 'list'})

    def test_renderer(self):
        request = factory.get('/locations/',
                              HTTP_ACCEPT=GeoJSONRenderer.media_type)
        response = self.view(request)
        self.assertIsInstance(response.accepted_renderer, GeoJSONRenderer)

    def test_register(self):
        self.assertGreater(len(self.router.urls), 0)


class RasterViewSetTestCase(SimpleTestCase):
    def setUp(self):
        self.router = DefaultRouter()
        self.router.register(r'rasters', RasterViewSet)
        self.view = RasterViewSet.as_view({'get': 'list'})

    def test_renderer(self):
        request = factory.get('/rasters/',
                              HTTP_ACCEPT=GeoTIFFZipRenderer.media_type)
        response = self.view(request)
        self.assertEqual(response['Content-Type'],
                         GeoTIFFZipRenderer.media_type)

    def test_register(self):
        self.assertGreater(len(self.router.urls), 0)
