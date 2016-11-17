from django.http import FileResponse
from django.forms import ValidationError as FormValidationError
from rest_framework import exceptions
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveAPIView
from rest_framework.serializers import ValidationError
from rest_framework.settings import api_settings
import rest_framework.renderers as rn

from spillway import filters, forms, mixins, pagination, renderers, serializers

_default_filters = tuple(api_settings.DEFAULT_FILTER_BACKENDS)
_default_renderers = tuple(api_settings.DEFAULT_RENDERER_CLASSES)


class BaseGeoView(mixins.ModelSerializerMixin):
    """Base view for models with geometry fields."""
    model_serializer_class = serializers.FeatureSerializer
    pagination_class = pagination.FeaturePagination
    filter_backends = _default_filters + (
        filters.SpatialLookupFilter, filters.GeoQuerySetFilter)
    renderer_classes = _default_renderers + (
        renderers.GeoJSONRenderer, renderers.KMLRenderer, renderers.KMZRenderer)


class GeoDetailView(BaseGeoView, RetrieveAPIView):
    """Generic detail view providing vector geometry representations."""


class GeoListView(BaseGeoView, ListAPIView):
    """Generic view for listing a geoqueryset."""


class GeoListCreateAPIView(BaseGeoView, ListCreateAPIView):
    """Generic view for listing or creating geomodel instances."""


class BaseRasterView(mixins.ModelSerializerMixin,
                     mixins.ResponseExceptionMixin):
    """Base view for raster models."""
    model_serializer_class = serializers.RasterModelSerializer
    filter_backends = _default_filters + (filters.RasterQuerySetFilter,)
    renderer_classes = _default_renderers + (
        renderers.GeoTIFFZipRenderer,
        renderers.HFAZipRenderer,
    )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super(BaseRasterView, self).finalize_response(
            request, response, *args, **kwargs)
        # Use streaming file responses for GDAL formats.
        if isinstance(getattr(response, 'accepted_renderer', None),
                      renderers.gdal.BaseGDALRenderer):
            headers = response._headers
            response = FileResponse(response.rendered_content)
            response._headers = headers
        return response

    def get_queryset(self):
        # Filter first so later RasterQuerySet methods always see a subset
        # instead of all available records.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        if lookup_url_kwarg in self.kwargs:
            filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
            return self.queryset.filter(**filter_kwargs)
        return self.queryset.all()

    def options(self, request, *args, **kwargs):
        if isinstance(self.request.accepted_renderer,
                      renderers.gdal.BaseGDALRenderer):
            raise exceptions.NotAcceptable
        return super(BaseRasterView, self).options(request, *args, **kwargs)

    @property
    def paginator(self):
        # Disable pagination for GDAL Renderers.
        if not isinstance(self.request.accepted_renderer,
                          _default_renderers):
            self.pagination_class = None
        return super(BaseRasterView, self).paginator


class RasterDetailView(BaseRasterView, RetrieveAPIView):
    """View providing access to a Raster model instance."""
    renderer_classes = _default_renderers + (
        renderers.GeoTIFFRenderer,
        renderers.HFARenderer,
    )


class RasterListView(BaseRasterView, ListAPIView):
    """View providing access to a Raster model QuerySet."""
    filter_backends = _default_filters + (
        filters.SpatialLookupFilter,
        filters.RasterQuerySetFilter,
    )
