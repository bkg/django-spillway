from django.contrib.gis.shortcuts import render_to_kml, render_to_kmz
from rest_framework.renderers import BaseRenderer
from rest_framework.pagination import PaginationSerializer

from spillway.collections import FeatureCollection


class BaseGeoRenderer(BaseRenderer):
    """Base renderer for geographic features."""

    def _collection(self, data, renderer_context=None):
        pageinfo = {}
        results_field = self._results_field(renderer_context)
        results = data
        if isinstance(data, dict):
            if results_field in data:
                results = data.pop(results_field)
                pageinfo = data
            else:
                results = [data]
        return FeatureCollection(features=results, **pageinfo)

    def _results_field(self, context):
        """Returns the view's pagination serializer results field or the
        default value.
        """
        try:
            view = context.get('view')
            return view.pagination_serializer_class.results_field
        except AttributeError:
            return PaginationSerializer.results_field


class GeoJSONRenderer(BaseGeoRenderer):
    """Renderer which encodes to GeoJSON.

    This renderer purposefully avoids reserialization of GeoJSON from the
    spatial backend which greatly improves performance.
    """
    media_type = 'application/geojson'
    format = 'geojson'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Returns *data* encoded as GeoJSON."""
        return str(self._collection(data, renderer_context))


class KMLRenderer(BaseGeoRenderer):
    """Renderer which encodes to KML."""
    media_type = 'application/vnd.google-earth.kml+xml'
    format = 'kml'
    template = 'spillway/placemarks.kml'

    def get_render_callable(self):
        return render_to_kml

    def render(self, data, accepted_media_type=None, renderer_context=None):
        collection = self._collection(data, renderer_context)
        return self.get_render_callable()(
            self.template, {'places': collection['features']})


class KMZRenderer(KMLRenderer):
    """Renderer which encodes to KMZ."""
    media_type = 'application/vnd.google-earth.kmz'
    format = 'kmz'

    def get_render_callable(self):
        return render_to_kmz
