import json

from spillway.query import GeoQuerySet
from spillway.models import GeoManager
from django.contrib.gis.db import models

_geom = {
    'type': 'Polygon',
    'coordinates': [[
        [ -64.95, -31.42 ],
        [ -61.69, -28.22 ],
        [ -61.61, -32.39 ],
        [ -64.95, -31.42 ]
    ]]
}


class Location(models.Model):
    name = models.CharField(max_length=30)
    geom = models.GeometryField()
    objects = GeoManager()

    def __str__(self):
        return self.name

    @classmethod
    def create(cls, **defaults):
        data = {'name': 'Vancouver',
                'geom': json.dumps(defaults.pop('geom', _geom))}
        data.update(**defaults)
        obj = cls(**data)
        obj.save()
        return obj
