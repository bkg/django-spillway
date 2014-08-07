import os
import shutil
import zipfile
import tempfile

from django.contrib.gis import forms
from django.contrib.gis import gdal
from django.contrib.gis.db.models.sql.query import ALL_TERMS

from spillway.forms.fields import (BoundingBoxField, OGRGeometryField,
    SpatialReferenceField)


class SpatialQueryForm(forms.Form):
    """Base spatial query form."""
    bbox = BoundingBoxField(required=False)


class GeometryQueryForm(SpatialQueryForm):
    """Geometry filter and spatial lookup query form."""
    geom = forms.GeometryField(required=False)
    # Tolerance value for geometry simplification
    simplify = forms.FloatField(required=False)
    srs = SpatialReferenceField(required=False)

    def __init__(self, *args, **kwargs):
        super(GeometryQueryForm, self).__init__(*args, **kwargs)
        self._spatial_lookup = None
        self._set_spatial_lookup()

    def _set_spatial_lookup(self):
        geom_field = self['geom']
        fieldname = geom_field.name
        for lookup in self.data:
            if lookup in ALL_TERMS:
                self._spatial_lookup = lookup
                field = self.fields.pop(fieldname)
                self.fields.update({lookup: field})
                break

    def clean(self):
        cleaned_data = super(GeometryQueryForm, self).clean()
        # Look for "bbox" which is just an alias to "bboverlaps".
        if cleaned_data.get('bbox'):
            cleaned_data.pop(self._spatial_lookup, None)
            self._spatial_lookup = 'bboverlaps'
            cleaned_data[self._spatial_lookup] = cleaned_data.pop('bbox')
        return cleaned_data

    @property
    def cleaned_geodata(self):
        if not (self.is_valid() and self._spatial_lookup):
            return {}
        return {self._spatial_lookup: self.cleaned_data[self._spatial_lookup]}


class RasterQueryForm(SpatialQueryForm):
    """Validates format options for raster data."""
    g = OGRGeometryField(required=False)
    upload = forms.FileField(required=False)

    def clean_upload(self):
        """Returns an OGR Polygon geometry from the FileField."""
        field = self.cleaned_data.get('upload')
        if not field:
            return None
        filename = field.name
        tmpdir = None
        if zipfile.is_zipfile(field):
            tmpdir = tempfile.mkdtemp()
            zf = zipfile.ZipFile(field)
            # Extract all files from the temporary directory using only the
            # base file name, avoids security issues with relative paths in the
            # zip.
            for item in zf.namelist():
                tmpname = os.path.join(tmpdir, os.path.basename(item))
                with open(tmpname, 'wb') as f:
                    f.write(zf.read(item))
                    #shutil.copyfileobj(zf.open(item), f)
                if tmpname.endswith('.shp'):
                    filename = tmpname
        # Attempt to union all geometries from GDAL data source.
        try:
            geoms = gdal.DataSource(filename)[0].get_geoms()
            geom = reduce(lambda g1, g2: g1.union(g2), geoms)
            if not geom.srs:
                raise gdal.OGRException('Cannot determine SRS')
        except (gdal.OGRException, gdal.OGRIndexError):
            geom = None
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
        return geom

    def clean(self):
        """Return cleaned fields as a dict, determine which geom takes
        precedence.
        """
        cleaned = super(RasterQueryForm, self).clean()
        cleaned['g'] = (cleaned.pop('upload') or cleaned.pop('g') or
                        cleaned.pop('bbox'))
        return cleaned
