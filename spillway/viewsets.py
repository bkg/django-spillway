from rest_framework import viewsets, generics, mixins

from spillway.generics import BaseGeoView, BaseRasterView


class GenericGeoViewSet(BaseGeoView, viewsets.ViewSetMixin, generics.GenericAPIView):
    """A generic view set providing vector geometry representations."""


class ReadOnlyGeoModelViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericGeoViewSet
):
    """A geo-enabled view set with default list and retrieve actions."""


class GeoModelViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericGeoViewSet,
):
    """A geo-enabled view set with default create, retrieve, update,
    partial_update, destroy, and list actions.
    """


class GenericRasterViewSet(
    BaseRasterView, viewsets.ViewSetMixin, generics.GenericAPIView
):
    """A generic view set providing raster representations."""


class ReadOnlyRasterModelViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericRasterViewSet
):
    """A raster-enabled view set with default list and retrieve actions."""
