from django.contrib.gis.shortcuts import compress_kml
from django.template import loader, Context
from rest_framework.renderers import BaseRenderer
from rest_framework.pagination import PaginationSerializer

from spillway.collections import FeatureCollection


class BaseGeoRenderer(BaseRenderer):
    """Base renderer for geographic features."""

    def _collection(self, data, renderer_context=None):
        pageinfo = {}
        results_field = self._results_field(renderer_context)
        results = data
        if data and isinstance(data, dict):
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
    """Renderer which serializes to GeoJSON.

    This renderer purposefully avoids reserialization of GeoJSON from the
    spatial backend which greatly improves performance.
    """
    media_type = 'application/geojson'
    format = 'geojson'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Returns *data* encoded as GeoJSON."""
        return str(self._collection(data, renderer_context))


class TemplateRenderer(BaseGeoRenderer):
    """Template based feature renderer."""
    template_name = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        collection = self._collection(data, renderer_context)
        template = loader.get_template(self.template_name)
        return template.render(Context({'features': collection['features']}))


class KMLRenderer(TemplateRenderer):
    """Renderer which serializes to KML."""
    media_type = 'application/vnd.google-earth.kml+xml'
    format = 'kml'
    template_name = 'spillway/placemarks.kml'


class KMZRenderer(KMLRenderer):
    """Renderer which serializes to KMZ."""
    media_type = 'application/vnd.google-earth.kmz'
    format = 'kmz'

    def render(self, *args, **kwargs):
        kmldata = super(KMZRenderer, self).render(*args, **kwargs)
        return compress_kml(kmldata)


class SVGRenderer(TemplateRenderer):
    """Renderer which serializes to SVG."""
    media_type = 'image/svg+xml'
    format = 'svg'
    template_name = 'spillway/features.svg'
