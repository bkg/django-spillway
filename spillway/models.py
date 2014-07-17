from django.contrib.gis.db import models

from .query import GeoQuerySet


# Temporary solution until QuerySet.as_manager() is available in 1.7.
class GeoManager(models.GeoManager):
    def get_query_set(self):
        return GeoQuerySet(self.model, using=self._db)

    def __getattr__(self, name):
        return getattr(self.get_query_set(), name)
