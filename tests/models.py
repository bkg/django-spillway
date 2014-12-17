import json

from django.contrib.gis.db import models
from spillway.models import GeoManager, AbstractRasterStore

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
    def create(cls, **data):
        geom = data.pop('geom', _geom)
        if isinstance(geom, dict):
            geom = json.dumps(geom)
        defaults = {'name': 'Vancouver', 'geom': geom}
        defaults.update(**data)
        obj = cls(**defaults)
        obj.save()
        return obj


class RasterStore(AbstractRasterStore):
    objects = GeoManager()
