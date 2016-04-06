from django.http import Http404
from rest_framework.renderers import BaseRenderer


class MapnikRenderer(BaseRenderer):
    """Renders Mapnik stylesheets to tiled PNG."""
    media_type = 'image/png'
    format = 'png'
    charset = None
    render_style = 'binary'

    def render(self, map, accepted_media_type=None, renderer_context=None):
        response = renderer_context and renderer_context.get('response')
        if getattr(response, 'exception', False):
            raise Http404
        return map.render(self.format)


class MapnikJPEGRenderer(MapnikRenderer):
    """Renders Mapnik stylesheets to tiled JPEG."""
    media_type = 'image/jpeg'
    format = 'jpeg'
