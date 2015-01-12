from django.conf.urls import patterns, url
from spillway import views, generics
from tests.test_views import MyGeoListView

from .models import Location, RasterStore

_tile = r'(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)/$'

urlpatterns = patterns('',
    url(r'^vectiles/%s' % _tile,
        views.TileView.as_view(model=Location), name='location-tiles'),
    url(r'^maptiles/(?P<pk>\d+)/%s' % _tile,
        views.MapView.as_view(model=RasterStore), name='map-tiles'),
    url(
        r'^list/$', MyGeoListView.as_view(model=Location),
        name='locations-list')
)
