import json

from django.contrib.gis import geos
from django.contrib.gis.db import models
from spillway.models import AbstractRasterStore
from spillway.query import GeoQuerySet, RasterQuerySet

_geom = {
    'type': 'Polygon',
    'coordinates': [[
        [ -64.95, -31.42 ],
        [ -61.69, -28.22 ],
        [ -61.61, -32.39 ],
        [ -64.95, -31.42 ]
    ]]
}


class AbstractLocation(models.Model):
    name = models.CharField(max_length=30)
    geom = models.GeometryField()

    class Meta:
        abstract = True

    def __repr__(self):
        return '<%s: %s %s>' % (self.__class__.__name__, self.name, self.geom)

    def __str__(self):
        return self.name

    @classmethod
    def create(cls, **data):
        geom = data.pop('geom', _geom)
        if isinstance(geom, dict):
            geom = json.dumps(geom)
        defaults = {'name': 'Vancouver', 'geom': geom}
        defaults.update(**data)
        obj = cls(**defaults)
        obj.save()
        return obj

    @classmethod
    def add_buffer(cls, coord, radius, **data):
        return cls.create(geom=geos.Point(*coord).buffer(radius), **data)


class Location(AbstractLocation):
    objects = GeoQuerySet.as_manager()


class GeoLocation(AbstractLocation):
    objects = models.GeoManager()


class RasterStore(AbstractRasterStore):
    objects = RasterQuerySet.as_manager()
