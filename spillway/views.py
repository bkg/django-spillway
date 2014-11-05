import math

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
    # Geometry simplification tolerances based on tile zlevel, see
    # http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames.
    tolerances = [6378137 * 2 * math.pi / (2 ** (zoom + 8))
                  for zoom in range(20)]

    def filter_queryset(self, queryset):
        queryset = super(TileView, self).filter_queryset(queryset)
        form = forms.MapTile(self.kwargs)
        params = form.cleaned_data if form.is_valid() else {}
        bbox = params.get('bbox')
        # Tile grid uses 3857, but coordinates should be in 4326 commonly.
        tile_srid = 3857
        coord_srid = bbox.srid
        original_srid = queryset.geo_field.srid
        try:
            tolerance = self.tolerances[params['z']]
        except IndexError:
            tolerance = self.tolerances[-1]
        geom_wkt = bbox.ewkt
        queryset = (queryset.filter_geometry(intersects=geom_wkt)
                            .intersection(geom_wkt))
        for obj in queryset:
            geom = obj.intersection
            # Geometry must be in Web Mercator for simplification.
            if geom.srid != tile_srid:
                # Result of intersection does not have SRID set properly.
                if geom.srid is None:
                    geom.srid = original_srid
                geom.transform(tile_srid)
            geom = geom.simplify(tolerance, preserve_topology=True)
            geom.transform(coord_srid)
            obj.geojson = geom.geojson
        return queryset
