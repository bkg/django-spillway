from django.contrib.gis.db import models
from rest_framework.filters import BaseFilterBackend


class GeoQuerySetFilter(BaseFilterBackend):
    """A Filter for calling GeoQuerySet methods."""
    precision = 4

    def filter_queryset(self, request, queryset, view):
        # Should we let other filters handle this?
        if view.kwargs:
            queryset = queryset.filter(**view.kwargs)
        params = view.form.cleaned_data
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
        modelfield = queryset.query._geo_field()
        query = {'%s__%s' % (modelfield.name, key): val
                 for key, val in view.form.cleaned_geodata.items()}
        return queryset.filter(**query)
