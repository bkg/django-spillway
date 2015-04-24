from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListAPIView

from spillway import forms, renderers
from spillway.generics import BaseGeoView


class MapView(GenericAPIView):
    """View for rendering map tiles from /{z}/{x}/{y}/ tile coordinates."""
    renderer_classes = (renderers.MapnikRenderer, renderers.MapnikJPEGRenderer)

    def get_renderer_context(self):
        context = super(MapView, self).get_renderer_context()
        form = forms.MapTile(dict(self.request.QUERY_PARAMS.dict(),
                                  **context.pop('kwargs')))
        context.update(form.cleaned_data if form.is_valid() else {})
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_object())


class TileView(BaseGeoView, ListAPIView):
    """View for serving tiled GeoJSON from a GeoModel."""
    paginate_by = None
    renderer_classes = (renderers.GeoJSONRenderer,)

    def filter_queryset(self, queryset):
        queryset = super(TileView, self).filter_queryset(queryset)
        form = forms.MapTile(self.kwargs, queryset)
        form.select()
        return form.queryset
