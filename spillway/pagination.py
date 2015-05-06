from rest_framework import pagination
from rest_framework.response import Response

from spillway import query
from spillway.collections import NamedCRS


class FeaturePagination(pagination.PageNumberPagination):
    """Feature pagination by page number."""

    def get_paginated_response(self, data):
        paginator = self.page.paginator
        crs = NamedCRS(query.get_srid(paginator.object_list))
        data.update({'count': paginator.count,
                     'next': self.get_next_link(),
                     'previous': self.get_previous_link(),
                     'crs': crs})
        return Response(data)
