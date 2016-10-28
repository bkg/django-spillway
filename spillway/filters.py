from django.forms import ValidationError
from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend

from spillway import forms


class FormFilterBackend(BaseFilterBackend):
    queryset_form = None

    def filter_queryset(self, request, queryset, view):
        form = self.queryset_form.from_request(request, queryset, view)
        try:
            return form.query()
        except ValidationError:
            raise serializers.ValidationError(form.errors)


class GeoQuerySetFilter(FormFilterBackend):
    """A Filter for calling GeoQuerySet methods."""
    queryset_form = forms.GeometryQueryForm


class RasterQuerySetFilter(FormFilterBackend):
    """A Filter for calling RasterQuerySet methods."""
    queryset_form = forms.RasterQueryForm


class SpatialLookupFilter(FormFilterBackend):
    """A Filter providing backend supported spatial lookups like intersects,
    overlaps, etc.
    """
    queryset_form = forms.SpatialQueryForm


class TileFilter(FormFilterBackend):
    queryset_form = forms.VectorTileForm
