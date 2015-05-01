from rest_framework import pagination, serializers

from spillway.collections import NamedCRS


class NamedCRSField(serializers.Field):
    def to_representation(self, value):
        srid = (value.object_list.query.transformed_srid or
                value.object_list.geo_field.srid)
        return NamedCRS(srid)


class PaginatedFeatureSerializer(pagination.PaginationSerializer):
    crs = NamedCRSField(source='*')
    results_field = 'features'
