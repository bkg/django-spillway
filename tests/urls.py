from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from spillway import views
from spillway.urls import tilepath

from .models import Location, RasterStore
from .test_viewsets import RasterViewSet

router = DefaultRouter()
router.register(r'rasters', RasterViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(tilepath('^vectiles/'),
        views.TileView.as_view(queryset=Location.objects.all()),
        name='location-tiles'),
    url(tilepath('^maptiles/(?P<pk>\d+)/'),
        views.RasterTileView.as_view(queryset=RasterStore.objects.all()),
        name='map-tiles'),
]
