from django.contrib.gis import forms
from django.contrib.gis.gdal import OGRGeometry, OGRException
from django.contrib.gis.gdal.srs import SpatialReference, SRSException
from django.utils.translation import ugettext_lazy as _

from spillway.compat import json


class CommaSepFloatField(forms.FloatField):
    """A Field for parsing a comma separated list of numeric values."""
    default_error_messages = {
        'invalid': _(u'Enter a comma separated list of numbers.'),
        'max_value': _(u'Ensure each value is less than or equal to %(limit_value)s.'),
        'min_value': _(u'Ensure each value is greater than or equal to %(limit_value)s.'),
    }

    def to_python(self, value):
        "Normalize data to a list of floats."
        # Return an empty list if no input was given.
        if not value:
            return []
        return map(super(CommaSepFloatField, self).to_python, value.split(','))

    def run_validators(self, value):
        """Run validators for each item separately."""
        for i in value:
            super(CommaSepFloatField, self).run_validators(i)


class BoundingBoxField(CommaSepFloatField):
    """A Field for comma separated bounding box coordinates."""
    # Default to EPSG:4326.
    default_srid = 4326

    def to_python(self, value):
        """Returns a OGR Polygon from bounding box values."""
        # Return an empty list if no input was given.
        value = super(BoundingBoxField, self).to_python(value)
        try:
            bbox = OGRGeometry.from_bbox(value).geos
        except (ValueError, AttributeError):
            #raise forms.ValidationError('Not a valid bounding box.')
            return []
        bbox.srid = self.default_srid
        return bbox


class OGRGeometryField(forms.GeometryField):
    """A Field for creating OGR geometries."""
    default_srid = 4326

    def to_python(self, value):
        # Work with a single GeoJSON geometry or a Feature. Avoid parsing
        # overhead unless we have a true "Feature".
        if not value:
            return
        if '"Feature",' in value:
            d = json.loads(value)
            value = json.dumps(d.get('geometry'))
        try:
            geom = OGRGeometry(value)
        except (OGRException, TypeError, ValueError):
            raise forms.ValidationError(self.error_messages['invalid_geom'])
        # When no projection info is present, try a guess of 4326 which is
        # fairly common, this also sets geom.srs properly.
        if not geom.srs:
            geom.srid = self.default_srid
        return geom


class SpatialReferenceField(forms.IntegerField):
    """A Field for creating spatial reference objects."""

    def to_python(self, value):
        value = super(SpatialReferenceField, self).to_python(value)
        try:
            return SpatialReference(value)
        except (SRSException, TypeError):
            return None
