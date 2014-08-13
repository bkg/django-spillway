from django.contrib.gis.db import models
from rest_framework.filters import BaseFilterBackend

from spillway import forms


class GeoQuerySetFilter(BaseFilterBackend):
    """A Filter for calling GeoQuerySet methods."""
    precision = 4

    def filter_queryset(self, request, queryset, view):
        params = view.clean_params()
        tolerance, srs = map(params.get, ('simplify', 'srs'))
        srid = getattr(srs, 'srid', None)
        kwargs = {}
        if not view.wants_default_renderer():
            kwargs.update(precision=self.precision,
                          format=request.accepted_renderer.format)
        return queryset.simplify(tolerance, srid, **kwargs)


class SpatialLookupFilter(BaseFilterBackend):
    """A Filter providing backend supported spatial lookups like intersects,
    overlaps, etc.
    """

    def filter_queryset(self, request, queryset, view):
        form = forms.SpatialQueryForm(request.QUERY_PARAMS)
        params = form.cleaned_data if form.is_valid() else {}
        return queryset.filter_geometry(**params)
