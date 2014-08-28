from rest_framework.compat import patterns, url
from spillway import views

from .models import Location

urlpatterns = patterns('',
    url(r'^tiles/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)/$',
        views.TileView.as_view(model=Location), name='location-tiles'),
)
