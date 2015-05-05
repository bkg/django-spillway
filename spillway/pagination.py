from rest_framework import pagination
from rest_framework.response import Response

from spillway.collections import NamedCRS


class FeaturePagination(pagination.PageNumberPagination):
    """Feature pagination by page number."""

    def get_paginated_response(self, data):
        paginator = self.page.paginator
        queryset = paginator.object_list
        crs = NamedCRS(queryset.query.transformed_srid or
                       queryset.geo_field.srid)
        data.update({'count': paginator.count,
                     'next': self.get_next_link(),
                     'previous': self.get_previous_link(),
                     'crs': crs})
        return Response(data)
