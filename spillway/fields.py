"""Serializer fields"""
import collections

from django.contrib.gis import geos, forms
from django.db.models.query import QuerySet
from rest_framework import renderers
from rest_framework.fields import Field, FileField

from spillway.compat import json
from spillway.forms import fields


class GeometryField(Field):
    def bind(self, field_name, parent):
        try:
            renderer = parent.context["request"].accepted_renderer
        except (AttributeError, KeyError):
            pass
        else:
            obj = parent.root.instance
            try:
                has_format = renderer.format in obj.query.annotations
            except AttributeError:
                if not isinstance(obj, QuerySet):
                    try:
                        obj = obj[0]
                    except (IndexError, TypeError):
                        pass
                has_format = hasattr(obj, renderer.format)
            if has_format:
                self.source = renderer.format
        super(GeometryField, self).bind(field_name, parent)

    def get_attribute(self, instance):
        # SpatiaLite returns empty/invalid geometries in WKT or GeoJSON with
        # exceedingly high simplification tolerances.
        try:
            return super(GeometryField, self).get_attribute(instance)
        except geos.GEOSException:
            return None

    def to_internal_value(self, data):
        # forms.GeometryField cannot handle geojson dicts.
        if isinstance(data, collections.Mapping):
            data = json.dumps(data)
        field = fields.GeometryField(widget=forms.BaseGeometryWidget())
        return field.to_python(data)

    def to_representation(self, value):
        # Create a dict from the GEOSGeometry when the value is not previously
        # serialized from the spatial db.
        try:
            return {"type": value.geom_type, "coordinates": value.coords}
        # Value is already serialized as geojson, kml, etc.
        except AttributeError:
            return value
