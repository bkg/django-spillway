from rest_framework import pagination
from rest_framework.response import Response

from spillway.collections import NamedCRS
from spillway.query import get_srid


class FeaturePagination(pagination.PageNumberPagination):
    """Feature pagination by page number."""

    def get_paginated_response(self, data):
        paginator = self.page.paginator
        crs = NamedCRS(get_srid(paginator.object_list))
        data.update({'count': paginator.count,
                     'next': self.get_next_link(),
                     'previous': self.get_previous_link(),
                     'crs': crs})
        return Response(data)
