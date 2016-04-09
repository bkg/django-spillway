from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from spillway import generics, views

from .models import Location, RasterStore
from .test_viewsets import RasterViewSet

router = DefaultRouter()
router.register(r'rasters', RasterViewSet)

_format_suffix = r'(?:\.(?P<format>[\w.]+))?'
_tile = r'(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)%s/?$' % _format_suffix

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^vectiles/%s' % _tile,
        views.TileView.as_view(queryset=Location.objects.all()),
        name='location-tiles'),
    url(r'^maptiles/(?P<pk>\d+)/%s' % _tile,
        views.MapView.as_view(queryset=RasterStore.objects.all()),
        name='map-tiles'),
]
