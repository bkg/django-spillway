import io
import os
import shutil
import json
import zipfile

from django import forms
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.gis.gdal import OGRGeometry
from django.test import SimpleTestCase, TestCase
from osgeo import ogr, osr

from spillway.forms.fields import (
    OGRGeometryField,
    GeometryFileField,
    GeoFormatField,
    SpatialReferenceField,
)
from spillway.collections import Feature, NamedCRS
from spillway.validators import GeometrySizeValidator
from .models import _geom


def write_shp(path, gjson):
    proj = osr.SpatialReference(osr.SRS_WKT_WGS84)
    g = ogr.CreateGeometryFromJson(json.dumps(gjson))
    vdriver = ogr.GetDriverByName("ESRI Shapefile")
    ds = vdriver.CreateDataSource(path)
    layer = ds.CreateLayer("", proj, g.GetGeometryType())
    featdef = layer.GetLayerDefn()
    feature = ogr.Feature(featdef)
    feature.SetGeometry(g)
    layer.CreateFeature(feature)
    feature.Destroy()
    ds.Destroy()


class OGRGeometryFieldTestCase(SimpleTestCase):
    def setUp(self):
        self.field = OGRGeometryField()

    def test_dict(self):
        geom = self.field.to_python(_geom)
        self.assertEqual(json.loads(geom.geojson), _geom)

    def test_extent(self):
        ex = (0, 0, 10, 10)
        geom = self.field.to_python(",".join(map(str, ex)))
        self.assertEqual(geom.extent, ex)

    def test_feature(self):
        feature = Feature(geometry=_geom)
        geojson = str(feature)
        geom = self.field.to_python(geojson)
        self.assertEqual(json.loads(geom.geojson), feature["geometry"])
        geom = self.field.to_python(feature)
        self.assertEqual(json.loads(geom.geojson), feature["geometry"])

    def test_feature_srid(self):
        srid = 3857
        feature = Feature(geometry=_geom, crs=NamedCRS(srid))
        geom = self.field.to_python(str(feature))
        self.assertEqual(geom.srid, srid)

    def test_invalid(self):
        self.assertRaises(forms.ValidationError, self.field.to_python, "3")

    def test_size_validator(self):
        validator = GeometrySizeValidator(3 ** 2, 4326)
        field = OGRGeometryField(srid=validator.srid, validators=[validator])
        self.assertRaises(forms.ValidationError, field.clean, "0,0,5,5")

    def test_srid(self):
        srid = 4269
        geom = OGRGeometryField(srid=srid).to_python("POINT(0 0)")
        self.assertEqual(geom.srid, srid)


class GeometryFileFieldTestCase(SimpleTestCase):
    def setUp(self):
        self.field = GeometryFileField()
        self.fp = SimpleUploadedFile("geom.json", json.dumps(_geom).encode("ascii"))
        self.fp.seek(0)

    def test_to_python(self):
        self.assertIsInstance(self.field.to_python(self.fp), OGRGeometry)
        fp = SimpleUploadedFile("empty.json", b"{}")
        self.assertRaises(forms.ValidationError, self.field.to_python, fp)

    def test_feature_to_python(self):
        feature = Feature(geometry=_geom)
        self.fp.write(str(feature).encode("ascii"))
        self.fp.seek(0)
        v = self.field.to_python(self.fp)
        self.assertIsInstance(v, OGRGeometry)

    def test_shapefile(self):
        base = "dir/geofield.shp"
        path = default_storage.path(base)
        os.mkdir(os.path.dirname(path))
        write_shp(path, _geom)
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as zf:
            for ext in ("dbf", "prj", "shp", "shx"):
                fname = base.replace("shp", ext)
                with default_storage.open(fname) as fp:
                    zf.writestr(fname, fp.read())
        shutil.rmtree(os.path.dirname(path))
        upfile = SimpleUploadedFile("geofield.zip", b.getvalue())
        b.close()
        result = self.field.to_python(upfile)
        self.assertIsInstance(result, OGRGeometry)
        self.assertIsNotNone(result.srs)

    def test_zipfile(self):
        zfile = io.BytesIO()
        with zipfile.ZipFile(zfile, "w") as zf:
            zf.writestr(self.fp.name, self.fp.read())
        zfile.seek(0)
        upfile = SimpleUploadedFile("geofield.zip", zfile.read())
        zfile.close()
        self.assertIsInstance(self.field.to_python(upfile), OGRGeometry)

    def tearDown(self):
        self.fp.close()


class GeoFormatFieldTestCase(SimpleTestCase):
    def test_to_python(self):
        field = GeoFormatField()
        self.assertRaises(forms.ValidationError, field.to_python, "invalid")
