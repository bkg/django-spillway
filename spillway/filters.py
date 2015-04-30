from rest_framework import exceptions
from rest_framework.filters import BaseFilterBackend

from spillway import forms


class FormFilterBackend(BaseFilterBackend):
    queryset_form = None

    def filter_queryset(self, request, queryset, view):
        params = dict(request.query_params.dict(),
                      format=request.accepted_renderer.format,
                      **getattr(view, 'kwargs', {}))
        form = self.queryset_form(params, queryset)
        try:
            form.query()
        except ValueError:
            raise exceptions.ParseError(form.errors)
        return form.queryset


class GeoQuerySetFilter(FormFilterBackend):
    """A Filter for calling GeoQuerySet methods."""
    queryset_form = forms.GeometryQueryForm


class SpatialLookupFilter(FormFilterBackend):
    """A Filter providing backend supported spatial lookups like intersects,
    overlaps, etc.
    """
    queryset_form = forms.SpatialQueryForm


class TileFilter(FormFilterBackend):
    queryset_form = forms.MapTile
