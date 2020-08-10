import os

from django.test import TestCase
from django.contrib.gis import geos
from django.contrib.gis.db.models import functions
from django.core.files.storage import default_storage
import greenwich

from spillway import forms, query
from spillway.models import upload_to
from spillway.query import GeoQuerySet
from .models import Location, RasterStore
from .test_models import RasterStoreTestBase, create_image


class GeoQuerySetTestCase(TestCase):
    def setUp(self):
        self.srid = 3857
        # Simplification tolerance in meters for EPSG 3857.
        self.tol = 10000
        # Buffer radius in degrees for EPSG 4326.
        self.radius = 2
        Location.add_buffer((0.1, 0.1), self.radius)
        self.qs = Location.objects.all()

    def test_extent(self):
        ex = self.qs.extent(self.srid)
        self.assertEqual(len(ex), 4)
        self.assertLess(ex[0], -180)
        ex2 = self.qs.extent()
        self.assertNotEqual(ex, ex2)

    def test_empty_extent(self):
        self.qs.delete()
        self.assertEqual(self.qs.extent(self.srid), None)

    def test_filter_geometry(self):
        qs = self.qs.filter_geometry(contains=self.qs[0].geom.centroid)
        self.assertEqual(qs.count(), 1)

    def test_simplify_geojson(self):
        fn = functions.AsGeoJSON(
            query.Simplify(functions.Transform("geom", self.srid), self.tol),
            precision=2,
        )
        sqs = self.qs.all().annotate(geojson=fn)
        geom = geos.GEOSGeometry(sqs[0].geojson, self.srid)
        source = self.qs[0].geom
        self.assertNotEqual(geom, source)
        self.assertNotEqual(geom.srid, source.srid)
        self.assertLess(geom.num_coords, source.num_coords)

    def test_simplify_kml(self):
        fn = functions.AsKML(query.Simplify("geom", self.radius))
        sqs = self.qs.all().annotate(kml=fn)
        self.assertTrue(sqs[0].kml.startswith("<Polygon>"))
        self.assertNotIn("<coordinates></coordinates>", sqs[0].kml)
        self.assertXMLNotEqual(sqs[0].kml, self.qs[0].geom.kml)

    def test_tile_pbf(self):
        tf = forms.VectorTileForm({"z": 6, "x": 32, "y": 32})
        self.assertTrue(tf.is_valid())
        qs = self.qs.tile(tf.cleaned_data["bbox"], tf.cleaned_data["z"], format="pbf")
        self.assertTrue(qs[0].pbf.startswith("POLYGON((1523.577271 4112"))


class RasterQuerySetTestCase(RasterStoreTestBase):
    use_multiband = True

    def setUp(self):
        for fp in self._files:
            relpath = fp.name.replace("%s/" % default_storage.location, "")
            RasterStore.objects.create(image=relpath)
        self.qs = RasterStore.objects.all()
        self.object = self.qs[0]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._files = [cls.f, create_image(cls.use_multiband)]

    @classmethod
    def tearDownClass(cls):
        for fp in cls._files:
            fp.close()
        super().tearDownClass()

    def test_aggregate_periods(self):
        qs = self.qs.aggregate_periods(3)
        self.assertEqual(qs[0].image.tolist(), [24.5, 37, 49.5])

    def test_summarize(self):
        qs = self.qs.summarize(self.object.geom.centroid)
        arraycenters = [12, 37, 62]
        self.assertEqual(list(qs[0].image), arraycenters)

    def test_summarize_point(self):
        qs = self.qs.summarize(geos.Point(-9999, -9999))
        self.assertEqual(list(qs[0].image), [])
        self.assertEqual(list(qs.get(pk=1).image), [])
        self.assertRaises(TypeError, qs.summarize, (1, 1))

    def test_summarize_polygon(self):
        geom = self.object.geom.buffer(-3)
        qs = self.qs.summarize(geom, "mean")
        means = [9, 34, 59]
        self.assertEqual(qs[0].image.tolist(), means)

    def test_warp(self):
        srid = 3857
        obj = self.qs[0]
        qs = self.qs.warp(srid, format="img")
        newobj = qs[0]
        r = newobj.raster()
        self.assertEqual(r.driver.ext, "img")
        self.assertIn("proj=merc", r.sref.proj4)
        self.assertEqual(r.sref.srid, srid)
        source = obj.raster()
        self.assertNotEqual(r.sref.srid, source.sref.srid)
        self.assertIsNone(newobj.pk)
        expected = os.path.join(upload_to.path, newobj.image.name)
        newobj.save()
        self.assertIsNotNone(newobj.pk)
        self.assertEqual(newobj.image.name, expected)
        self.assertTrue(default_storage.exists(newobj.image))
