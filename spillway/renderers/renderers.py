from django.contrib.gis.shortcuts import compress_kml
from django.template import loader, Context
from rest_framework.renderers import BaseRenderer, JSONRenderer

from spillway import collections


class GeoJSONRenderer(JSONRenderer):
    """Renderer which serializes to GeoJSON.

    This renderer purposefully avoids reserialization of GeoJSON from the
    spatial backend which greatly improves performance.
    """
    media_type = 'application/vnd.geo+json'
    format = 'geojson'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Returns *data* encoded as GeoJSON."""
        data = collections.as_feature(data)
        try:
            return data.geojson
        except AttributeError:
            return super(GeoJSONRenderer, self).render(
                data, accepted_media_type, renderer_context)


class TemplateRenderer(BaseRenderer):
    """Template based feature renderer."""
    template_name = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        collection = collections.as_feature(data)
        try:
            features = collection['features']
        except KeyError:
            features = [collection]
        template = loader.get_template(self.template_name)
        return template.render(Context({'features': features}))


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


class MapnikRenderer(BaseRenderer):
    """Renders Mapnik stylesheets to tiled PNG."""
    media_type = 'image/png'
    format = 'png'
    charset = None
    render_style = 'binary'

    def render(self, imgdata, accepted_media_type=None, renderer_context=None):
        # Just a no-op renderer as the mapnik map object should be serialized
        # prior to take full advantage of the caching framework.
        return imgdata


class MapnikJPEGRenderer(MapnikRenderer):
    """Renders Mapnik stylesheets to tiled JPEG."""
    media_type = 'image/jpeg'
    format = 'jpeg'
