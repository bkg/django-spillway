from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListAPIView

from spillway import filters, forms, renderers
from spillway.generics import BaseGeoView


class MapView(GenericAPIView):
    """View for rendering map tiles from /{z}/{x}/{y}/ tile coordinates."""
    renderer_classes = (renderers.MapnikRenderer, renderers.MapnikJPEGRenderer)

    def get_renderer_context(self):
        context = super(MapView, self).get_renderer_context()
        form = forms.MapTile(dict(self.request.query_params.dict(),
                                  **context.pop('kwargs')))
        context.update(form.cleaned_data if form.is_valid() else {})
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_object())


class TileView(BaseGeoView, ListAPIView):
    """View for serving tiled GeoJSON from a GeoModel."""
    pagination_class = None
    filter_backends = (filters.TileFilter,)
    renderer_classes = (renderers.GeoJSONRenderer,)
