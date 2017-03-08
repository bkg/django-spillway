from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListAPIView

from spillway import carto, filters, forms, mixins, renderers
from spillway.generics import BaseGeoView


class RasterTileView(mixins.ResponseExceptionMixin, GenericAPIView):
    """View for rendering map tiles from /{z}/{x}/{y}/ tile coordinates."""
    renderer_classes = (renderers.MapnikRenderer,
                        renderers.MapnikJPEGRenderer)

    def get(self, request, *args, **kwargs):
        form = forms.RasterTileForm.from_request(request, view=self)
        m = carto.build_map([self.get_object()], form)
        # Mapnik Map object is not pickleable, so it breaks the caching
        # middleware. We must serialize the image before passing it off to the
        # Response and Renderer.
        return Response(m.render(request.accepted_renderer.format))


class TileView(mixins.ResponseExceptionMixin, BaseGeoView, ListAPIView):
    """View for serving tiled GeoJSON or PNG from a GeoModel."""
    pagination_class = None
    filter_backends = (filters.TileFilter,)
    renderer_classes = (renderers.GeoJSONRenderer, renderers.MapnikRenderer)

    def get(self, request, *args, **kwargs):
        if isinstance(request.accepted_renderer,
                      renderers.GeoJSONRenderer):
            return super(TileView, self).get(request, *args, **kwargs)
        form = forms.RasterTileForm.from_request(request, view=self)
        m = carto.build_map([self.get_queryset()], form)
        return Response(m.render(request.accepted_renderer.format))
