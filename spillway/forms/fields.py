import os
import collections
import shutil
import tempfile
import zipfile

from django.contrib.gis import forms, gdal
from django.contrib.gis.gdal.srs import SpatialReference, SRSException
from django.utils.translation import ugettext_lazy as _
from greenwich.geometry import Envelope

import spillway.collections as sc
from spillway.compat import json


class CommaSepFloatField(forms.FloatField):
    """A form Field for parsing a comma separated list of numeric values."""
    default_error_messages = {
        'invalid': _(u'Enter a comma separated list of numbers.'),
        'max_value': _(u'Ensure each value is less than or equal to %(limit_value)s.'),
        'min_value': _(u'Ensure each value is greater than or equal to %(limit_value)s.'),
    }

    def to_python(self, value):
        "Normalize data to a list of floats."
        if not value:
            return []
        return map(super(CommaSepFloatField, self).to_python, value.split(','))

    def run_validators(self, values):
        """Run validators for each item separately."""
        for val in values:
            super(CommaSepFloatField, self).run_validators(val)


class BoundingBoxField(CommaSepFloatField):
    """A form Field for comma separated bounding box coordinates."""

    def __init__(self, srid=4326, *args, **kwargs):
        super(BoundingBoxField, self).__init__(*args, **kwargs)
        self.srid = srid

    def to_python(self, value):
        """Returns a GEOS Polygon from bounding box values."""
        value = super(BoundingBoxField, self).to_python(value)
        try:
            bbox = gdal.OGRGeometry.from_bbox(value).geos
        except (ValueError, AttributeError):
            return []
        bbox.srid = self.srid
        return bbox


class GeometryField(forms.GeometryField):
    """A form Field for creating GEOS geometries."""

    def to_python(self, value):
        # Need to catch GDALException with some invalid geometries, the
        # parent class doesn't handle all cases.
        try:
            return super(GeometryField, self).to_python(value)
        except gdal.GDALException:
            raise forms.ValidationError(
                self.error_messages['invalid_geom'], code='invalid_geom')


class GeometryFileField(forms.FileField):
    """A form Field for creating OGR geometries from file based sources."""

    def to_python(self, value):
        value = super(GeometryFileField, self).to_python(value)
        if value is None:
            return value
        filename = value.name
        tmpdir = None
        if zipfile.is_zipfile(value):
            tmpdir = tempfile.mkdtemp()
            zf = zipfile.ZipFile(value)
            # Extract all files from the temporary directory using only the
            # base file name, avoids security issues with relative paths in the
            # zip.
            for item in sorted(zf.namelist()):
                filename = os.path.join(tmpdir, os.path.basename(item))
                with open(filename, 'wb') as f:
                    f.write(zf.read(item))
        # Attempt to union all geometries from GDAL data source.
        try:
            geoms = gdal.DataSource(filename)[0].get_geoms()
            geom = reduce(lambda g1, g2: g1.union(g2), geoms)
            if not geom.srs:
                raise gdal.OGRException('Cannot determine SRS')
        except (gdal.OGRException, gdal.OGRIndexError):
            geom = None
        finally:
            if tmpdir and os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir)
        return geom


class OGRGeometryField(forms.GeometryField):
    """A form Field for creating OGR geometries."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        sref = None
        # Work with a single GeoJSON geometry or a Feature.
        value = json.loads(value) if '"Feature",' in value else value
        if isinstance(value, collections.Mapping):
            feat = sc.as_feature(value)
            value = json.dumps(feat.get('geometry') or value)
            sref = feat.srs
        # Handle a comma delimited extent.
        elif list(value).count(',') == 3:
            value = Envelope(value.split(',')).polygon.ExportToWkt()
        try:
            geom = gdal.OGRGeometry(value, srs=getattr(sref, 'wkt', None))
        except (gdal.OGRException, TypeError, ValueError):
            raise forms.ValidationError(self.error_messages['invalid_geom'])
        if not geom.srs:
            geom.srid = self.srid or self.widget.map_srid
        return geom


class SpatialReferenceField(forms.IntegerField):
    """A form Field for creating spatial reference objects."""

    def to_python(self, value):
        value = super(SpatialReferenceField, self).to_python(value)
        if value in self.empty_values:
            return None
        try:
            return SpatialReference(value)
        except (SRSException, TypeError):
            return None
