from rest_framework.filters import DjangoFilterBackend
from rest_framework.generics import ListAPIView
from rest_framework.settings import api_settings

from spillway import filters, forms, mixins, renderers, serializers


class BaseGeoView(mixins.QueryFormMixin):
    """Base view for models with geometry fields."""
    serializer_class = serializers.FeatureSerializer
    query_form_class = forms.GeometryQueryForm
    # Set in subclasses or via as_view()
    model = None

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
        if not getattr(cls.Meta, 'model', False):
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

    def get_paginate_by(self, queryset=None):
        """Return the size of pages to use or None to skip pagination."""
        # Do not paginate unless we are explicitly told to do so, avoids an
        # unecessary LIMIT query.
        if self.page_kwarg in self.request.QUERY_PARAMS:
            return super(GeoListView, self).get_paginate_by(queryset)
        return None
