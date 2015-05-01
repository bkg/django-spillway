from django.conf.urls import patterns, url
from spillway import views

from .models import Location, RasterStore

_tile = r'(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)/$'

urlpatterns = patterns('',
    url(r'^vectiles/%s' % _tile,
        views.TileView.as_view(queryset=Location.objects.all()),
        name='location-tiles'),
    url(r'^maptiles/(?P<pk>\d+)/%s' % _tile,
        views.MapView.as_view(queryset=RasterStore.objects.all()),
        name='map-tiles'),
)
