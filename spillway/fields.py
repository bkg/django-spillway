"""Serializer fields"""
import os

from django.contrib.gis import forms
from rest_framework.fields import Field, FileField
from greenwich.io import MemFileIO
from greenwich.raster import Raster, driver_for_path

from spillway.compat import json


class GeometryField(Field):
    def to_internal_value(self, data):
        # forms.GeometryField cannot handle geojson dicts.
        if isinstance(data, dict):
            data = json.dumps(data)
        return forms.GeometryField().to_python(data)

    def to_representation(self, value):
        # Create a dict from the GEOSGeometry when the value is not previously
        # serialized from the spatial db.
        try:
            return {'type': value.geom_type, 'coordinates': value.coords}
        # Value is already serialized as geojson, kml, etc.
        except AttributeError:
            return value


class NDArrayField(FileField):
    def to_representation(self, value):
        geom = self.context.get('g')
        stat = self.context.get('stat')
        with Raster(getattr(value, 'path', value)) as r:
            if geom:
                with r.clip(geom) as clipped:
                    arr = clipped.masked_array()
            else:
                arr = r.masked_array()
        return arr if not stat else getattr(arr, stat)()


class GDALField(FileField):
    def to_representation(self, value):
        imgpath = value.path
        geom = self.context.get('g')
        # Handle format as .tif, tif, or tif.zip
        ext = self.context.get('format') or os.path.splitext(imgpath)[-1][1:]
        ext = os.path.splitext(ext)[0]
        # No conversion is needed if the original format without clipping
        # is requested.
        if not geom and imgpath.endswith(ext):
            return imgpath
        driver = driver_for_path('base.%s' % ext)
        memio = MemFileIO()
        if geom:
            with Raster(imgpath) as r:
                with r.clip(geom) as clipped:
                    clipped.save(memio, driver)
        else:
            driver.copy(imgpath, memio.name)
        return memio
