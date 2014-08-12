from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.settings import api_settings

from spillway import filters, forms, mixins, renderers, serializers


class BaseGeoView(mixins.QueryFormMixin):
    """Base view for models with geometry fields."""
    serializer_class = serializers.FeatureSerializer
    query_form_class = forms.GeometryQueryForm

    def initial(self, request, *args, **kwargs):
        super(BaseGeoView, self).initial(request, *args, **kwargs)
        # Attempt to set the model if the serializer has one defined.
        if not self.model:
            self.model = getattr(self.serializer_class.Meta, 'model', None)

    def get_serializer_class(self):
        cls = self.serializer_class
        # Make sure we have a model set for the serializer, allows calling
        # .as_view() with a model param only since serializer_class is already
        # set here.
        if self.model and getattr(cls.Meta, 'model', False) != self.model:
            cls.Meta.model = self.model
        return cls

    def wants_default_renderer(self):
        """Returns true when using a default renderer class."""
        return isinstance(self.request.accepted_renderer,
                          tuple(api_settings.DEFAULT_RENDERER_CLASSES))


class GeoListView(BaseGeoView, ListAPIView):
    """Generic list view providing vector geometry representations."""
    renderer_classes = tuple(ListAPIView.renderer_classes) + (
        renderers.GeoJSONRenderer, renderers.KMLRenderer, renderers.KMZRenderer)
    filter_backends = (filters.SpatialLookupFilter, filters.GeoQuerySetFilter)


class BaseRasterView(BaseGeoView):
    """Base view for raster models."""
    serializer_class = serializers.RasterModelSerializer
    query_form_class = forms.RasterQueryForm

    def get_serializer_context(self):
        context = super(BaseRasterView, self).get_serializer_context()
        context.update(params=self.clean_params())
        return context


class RasterListView(BaseRasterView, ListAPIView):
    """View for read only access to a Raster model QuerySet."""
    filter_backends = (filters.SpatialLookupFilter,)
    renderer_classes = tuple(ListAPIView.renderer_classes) + (
        renderers.HFAZipRenderer,
        renderers.GeoTIFFZipRenderer,
    )


class RasterDetailView(BaseRasterView, RetrieveAPIView):
    """View for read only access to a Raster model instance."""
    renderer_classes = tuple(RetrieveAPIView.renderer_classes) + (
        renderers.HFARenderer,
        renderers.GeoTIFFRenderer
    )
