import os
import collections
import shutil
import tempfile
import zipfile

from django.utils.six.moves import reduce
from django.contrib.gis import forms, gdal
from django.contrib.gis.db.models import functions
from django.contrib.gis.gdal.srs import SpatialReference, SRSException
from django.utils.translation import ugettext_lazy as _
from greenwich.geometry import Envelope
from rest_framework import renderers

from spillway import query, collections as sc
from spillway.compat import json


class CommaSepFloatField(forms.FloatField):
    """A form Field for parsing a comma separated list of numeric values."""
    default_error_messages = {
        'invalid': _('Enter a comma separated list of numbers.'),
        'max_value': _('Ensure each value is less than or equal to %(limit_value)s.'),
        'min_value': _('Ensure each value is greater than or equal to %(limit_value)s.'),
    }

    def to_python(self, value):
        """Normalize data to a list of floats."""
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


class GeoFormatField(forms.CharField):
    default_error_messages = {
        'invalid_geofunc': _('%(value)s is not a supported function.'),
    }
    funcs = {'centroid': 'Centroid',
             'pointonsurface': 'PointOnSurface',
             'geojson': 'AsGeoJSON',
             'gml': 'AsGML',
             'kml': 'AsKML',
             'svg': 'AsSVG'}

    def to_python(self, value):
        if value in self.empty_values + [renderers.JSONRenderer.format]:
            return None
        # Skip known DRF renderer formats.
        formats = [renderers.BrowsableAPIRenderer.format,
                   renderers.TemplateHTMLRenderer.format]
        if value in formats:
            return query.AsText
        try:
            fn = getattr(functions, self.funcs[value])
        except (KeyError, AttributeError):
            raise forms.ValidationError(self.error_messages['invalid_geofunc'],
                                        code='invalid_geofunc')
        if fn.arity and fn.arity > 1:
            raise forms.ValidationError('Not yet supported')
        return fn


class GeometryField(forms.GeometryField):
    """A form Field for creating GEOS geometries."""

    def to_python(self, value):
        # Need to catch GDALException with some invalid geometries, the
        # parent class doesn't handle all cases.
        try:
            return super(GeometryField, self).to_python(value)
        except gdal.GDALException:
            raise forms.ValidationError(self.error_messages['invalid_geom'],
                                        code='invalid_geom')



class GeometryFileField(forms.FileField):
    """A form Field for creating OGR geometries from file based sources."""

    def _from_file(self, fileobj, tmpdir):
        if zipfile.is_zipfile(fileobj):
            with zipfile.ZipFile(fileobj) as zf:
                extracted = []
                for item in zf.infolist():
                    fname = os.path.abspath(os.path.join(tmpdir, item.filename))
                    if fname.startswith(tmpdir):
                        zf.extract(item, tmpdir)
                        extracted.append(fname)
                for path in extracted:
                    if path.endswith('.shp'):
                        fname = path
        else:
            # NOTE: is_zipfile() seeks to end of file or at least 110 bytes.
            fileobj.seek(0)
            with tempfile.NamedTemporaryFile(dir=tmpdir, delete=False) as fp:
                shutil.copyfileobj(fileobj, fp)
            fname = fp.name
        # Attempt to union all geometries from GDAL data source.
        try:
            geoms = gdal.DataSource(fname)[0].get_geoms()
            geom = reduce(lambda g1, g2: g1.union(g2), geoms)
            if not geom.srs:
                raise gdal.OGRException('Cannot determine SRS')
        except (gdal.OGRException, gdal.OGRIndexError):
            raise forms.ValidationError(
                GeometryField.default_error_messages['invalid_geom'],
                code='invalid_geom')
        return geom

    def to_python(self, value):
        value = super(GeometryFileField, self).to_python(value)
        if value is None:
            return value
        try:
            tmpdir = tempfile.mkdtemp()
            return self._from_file(value, tmpdir)
        finally:
            shutil.rmtree(tmpdir)


class OGRGeometryField(forms.GeometryField):
    """A form Field for creating OGR geometries."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        sref = None
        # Work with a single GeoJSON geometry or a Feature.
        value = json.loads(value) if '"Feature"' in value else value
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
            raise forms.ValidationError(self.error_messages['invalid_geom'],
                                        code='invalid_geom')
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
