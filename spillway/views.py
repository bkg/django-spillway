from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListAPIView

from spillway import carto, filters, forms, renderers
from spillway.generics import BaseGeoView


class MapView(GenericAPIView):
    """View for rendering map tiles from /{z}/{x}/{y}/ tile coordinates."""
    renderer_classes = (renderers.MapnikRenderer,
                        renderers.MapnikJPEGRenderer)

    def get(self, request, *args, **kwargs):
        form = forms.RasterTileForm(dict(self.request.query_params.dict(),
                                    **self.kwargs))
        return Response(carto.build_map(self.get_object(), form))


class TileView(BaseGeoView, ListAPIView):
    """View for serving tiled GeoJSON or PNG from a GeoModel."""
    pagination_class = None
    filter_backends = (filters.TileFilter,)
    renderer_classes = (renderers.GeoJSONRenderer, renderers.MapnikRenderer)

    def get(self, request, *args, **kwargs):
        if isinstance(request.accepted_renderer,
                      renderers.GeoJSONRenderer):
            return super(TileView, self).get(request, *args, **kwargs)
        form = forms.VectorTileForm(dict(self.request.query_params.dict(),
                                    **self.kwargs))
        queryset = self.filter_queryset(self.get_queryset())
        return Response(carto.build_map(queryset, form))
