import os
import shutil
import zipfile
import tempfile

from django.contrib.gis import forms
from django.contrib.gis import gdal
from django.contrib.gis.gdal.srs import SpatialReference, SRSException
from django.utils.translation import ugettext_lazy as _
from greenwich.geometry import Envelope

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
            bbox = gdal.OGRGeometry.from_bbox(value).geos
        except (ValueError, AttributeError):
            #raise forms.ValidationError('Not a valid bounding box.')
            return []
        bbox.srid = self.default_srid
        return bbox


class GeometryFileField(forms.FileField):
    """A Field for creating OGR geometries from file based sources."""

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
            for item in zf.namelist():
                filename = os.path.join(tmpdir, os.path.basename(item))
                with open(filename, 'wb') as f:
                    f.write(zf.read(item))
                if filename.endswith('.shp'):
                    break
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
    """A Field for creating OGR geometries."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        # Work with a single GeoJSON geometry or a Feature. Avoid parsing
        # overhead unless we have a true "Feature".
        if '"Feature",' in value:
            d = json.loads(value)
            value = json.dumps(d.get('geometry'))
        # Handle a comma delimited extent.
        elif list(value).count(',') == 3:
            value = Envelope(value.split(',')).polygon.ExportToWkt()
        try:
            geom = gdal.OGRGeometry(value)
        except (gdal.OGRException, TypeError, ValueError):
            raise forms.ValidationError(self.error_messages['invalid_geom'])
        if not geom.srs:
            geom.srid = self.srid or self.widget.map_srid
        return geom


class SpatialReferenceField(forms.IntegerField):
    """A Field for creating spatial reference objects."""

    def to_python(self, value):
        value = super(SpatialReferenceField, self).to_python(value)
        try:
            return SpatialReference(value)
        except (SRSException, TypeError):
            return None
