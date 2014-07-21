from django.contrib.gis.shortcuts import render_to_kml, render_to_kmz
from rest_framework.renderers import BaseRenderer
from rest_framework.pagination import PaginationSerializer

from spillway.compat import json


class GeoJSONRenderer(BaseRenderer):
    """Renderer which encodes to GeoJSON.

    This renderer purposefully avoids reserialization of GeoJSON from the
    spatial backend which greatly improves performance.
    """
    media_type = 'application/geojson'
    format = 'geojson'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Returns *data* encoded as GeoJSON."""
        geom_key = 'geometry'
        pageinfo = ''
        seps = (',', ':')
        results_field = self._results_field(renderer_context)
        try:
            results = data.pop(results_field, [data])
        except TypeError:
            results = data
        else:
            if geom_key not in data:
                pageinfo = json.dumps(data, separators=seps).strip('{}') + ','
        collection = '{"type":"FeatureCollection",%s"features":[' % pageinfo
        feature = '{"geometry":%s,%s}'
        features = ','.join([feature % (rec.pop('geometry', '{}'),
                             json.dumps(rec, separators=seps)[1:-1]) for rec in results])
        # str.join is faster than string interp via '%' or str.format
        return ''.join([collection, features, ']}'])

    def _results_field(self, context):
        """Returns the view's pagination serializer results field or the
        default value.
        """
        try:
            view = context.get('view')
            return view.pagination_serializer_class.results_field
        except AttributeError:
            return PaginationSerializer.results_field


class KMLRenderer(BaseRenderer):
    """Renderer which encodes to KML."""
    media_type = 'application/vnd.google-earth.kml+xml'
    format = 'kml'
    template = 'spillway/placemarks.kml'

    def _results(self, data):
        try:
            results = data.pop('results', [data])
        except TypeError:
            results = data
        return results

    def get_render_callable(self):
        return render_to_kml

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return self.get_render_callable()(
            self.template, {'places': self._results(data)})


class KMZRenderer(KMLRenderer):
    """Renderer which encodes to KMZ."""
    media_type = 'application/vnd.google-earth.kmz'
    format = 'kmz'

    def get_render_callable(self):
        return render_to_kmz
