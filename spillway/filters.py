from django.contrib.gis.db import models
from django.utils import six

from rest_framework.settings import api_settings
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
        if not isinstance(request.accepted_renderer,
                          tuple(api_settings.DEFAULT_RENDERER_CLASSES)):
            kwargs.update(precision=self.precision,
                          format=request.accepted_renderer.format)
        return queryset.simplify(tolerance, srid, **kwargs)


class SpatialLookupFilter(BaseFilterBackend):
    """A Filter providing backend supported spatial lookups like intersects,
    overlaps, etc.
    """

    def filter_queryset(self, request, queryset, view):
        query = {}
        modelfield = queryset.query._geo_field()
        geom_field = view.form[modelfield.name]
        for k in request.QUERY_PARAMS:
            if k.startswith(modelfield.name):
                name, lookup = k.split('_')
                if lookup in models.sql.query.ALL_TERMS:
                    val = geom_field.field.to_python(request.QUERY_PARAMS[k])
                    query = {'%s__%s' % (name, lookup): val}
        return queryset.filter(**query)
