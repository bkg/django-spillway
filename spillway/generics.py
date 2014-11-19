from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveAPIView
from rest_framework.settings import api_settings

from spillway import filters, forms, mixins, renderers, serializers

_default_renderers = tuple(api_settings.DEFAULT_RENDERER_CLASSES)


class BaseGeoView(mixins.QueryFormMixin):
    """Base view for models with geometry fields."""
    model_serializer_class = serializers.FeatureSerializer
    pagination_serializer_class = serializers.PaginatedFeatureSerializer
    query_form_class = forms.GeometryQueryForm
    renderer_classes = _default_renderers + (
        renderers.GeoJSONRenderer, renderers.KMLRenderer, renderers.KMZRenderer)

    def wants_default_renderer(self):
        """Returns true when using a default renderer class."""
        return isinstance(self.request.accepted_renderer, _default_renderers)


class GeoDetailView(BaseGeoView, RetrieveAPIView):
    """Generic detail view providing vector geometry representations."""


class GeoListView(BaseGeoView, ListAPIView):
    """Generic list view providing vector geometry representations."""
    filter_backends = (filters.SpatialLookupFilter, filters.GeoQuerySetFilter)


class GeoListCreateAPIView(BaseGeoView, ListCreateAPIView):
    filter_backends = (filters.SpatialLookupFilter, filters.GeoQuerySetFilter)


class BaseRasterView(BaseGeoView):
    """Base view for raster models."""
    model_serializer_class = serializers.RasterModelSerializer
    query_form_class = forms.RasterQueryForm

    def get_serializer_context(self):
        context = super(BaseRasterView, self).get_serializer_context()
        context.update(params=self.clean_params())
        return context


class RasterDetailView(BaseRasterView, RetrieveAPIView):
    """View providing access to a Raster model instance."""
    renderer_classes = _default_renderers + (
        renderers.GeoTIFFRenderer,
        renderers.HFARenderer,
    )


class RasterListView(BaseRasterView, ListAPIView):
    """View providing access to a Raster model QuerySet."""
    filter_backends = (filters.SpatialLookupFilter,)
    renderer_classes = _default_renderers + (
        renderers.GeoTIFFZipRenderer,
        renderers.HFAZipRenderer,
    )
