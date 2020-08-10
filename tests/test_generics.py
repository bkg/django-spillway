import re
import json
import io
import zipfile

from django.contrib.gis import geos
import django.contrib.gis.db.models.functions as sqlfn
from django.test import TestCase
from greenwich.raster import Raster
from rest_framework import status
from rest_framework.exceptions import NotAcceptable
from rest_framework.test import APIRequestFactory

from spillway import generics, forms
from spillway.renderers import GeoJSONRenderer, GeoTIFFZipRenderer
from .models import GeoLocation, Location
from .test_models import RasterStoreTestBase
from .test_serializers import LocationFeatureSerializer

factory = APIRequestFactory()


class PaginatedGeoListView(generics.GeoListView):
    pass


# Enable pagination for this view
PaginatedGeoListView.pagination_class.page_size = 10


class BaseGeoDetailViewTestCase(TestCase):
    model = GeoLocation
    precision = 4

    def setUp(self):
        self.radius = 5
        self.model.add_buffer((10, -10), self.radius)
        self.model.create()
        self.qs = self.model.objects.all()
        self.view = generics.GeoDetailView.as_view(queryset=self.qs)


class GeoDetailViewTestCase(BaseGeoDetailViewTestCase):
    url = "/glocations/1/"

    def test_api_response(self):
        response = self.client.get(self.url, HTTP_ACCEPT="text/html")
        wkt = re.search("POLYGON[^&]+", response.content.decode("utf-8")).group()
        g = geos.GEOSGeometry(wkt)
        self.assertEqual(g, self.qs[0].geom.wkt)

    def test_json_response(self):
        expected = json.loads(self.qs[0].geom.geojson)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        feature = response.json()
        self.assertAlmostEqual(feature["geometry"], expected)
        self.assertEqual(feature["type"], "Feature")

    def test_geojson_response(self):
        gj = self.qs.annotate(
            geojson=sqlfn.AsGeoJSON("geom", precision=self.precision)
        )[0].geojson
        expected = json.loads(gj)
        with self.assertNumQueries(1):
            response = self.client.get(
                self.url, {"format": "geojson", "precision": self.precision}
            )
        self.assertEqual(response.status_code, 200)
        feature = response.json()
        self.assertEqual(feature["geometry"], expected)
        self.assertEqual(feature["type"], "Feature")
        # Be sure we get geojson returned from SQL function call, not GEOS.
        sqlformat = '{"type":"Polygon","coordinates":[[['
        self.assertContains(response, 'geometry": %s' % sqlformat)

    def test_kml_response(self):
        response = self.client.get(
            self.url, {"format": "kml", "precision": self.precision}
        )
        part = self.qs.annotate(kml=sqlfn.AsKML("geom", precision=self.precision))[
            0
        ].kml
        self.assertInHTML(part, response.content.decode("utf-8"), count=1)


class GeoManagerDetailViewTestCase(BaseGeoDetailViewTestCase):
    model = Location
    url = "/locations/1/"

    def test_simplify(self):
        response = self.client.get(
            self.url, {"simplify": self.radius, "format": "geojson"}
        )
        orig = self.qs.get(pk=1).geom
        serializer = LocationFeatureSerializer(data=response.json())
        self.assertTrue(serializer.is_valid())
        object = serializer.save()
        self.assertLess(object.geom.num_coords, orig.num_coords)
        self.assertNotEqual(object.geom, orig)
        self.assertEqual(object.geom.srid, orig.srid)


class GeoListViewTestCase(TestCase):
    url = "/locations/"

    def setUp(self):
        self.srid = Location.geom._field.srid
        records = [
            {"name": "Banff", "coordinates": [-115.554, 51.179]},
            {"name": "Jasper", "coordinates": [-118.081, 52.875]},
        ]
        for record in records:
            obj = Location.add_buffer(record.pop("coordinates"), 0.5, **record)
        self.qs = Location.objects.all()

    def _parse_collection(self, response, srid=None):
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), len(self.qs))
        for feature in data["features"]:
            yield geos.GEOSGeometry(json.dumps(feature["geometry"]), srid or self.srid)

    def test_list(self):
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["features"]), len(self.qs))

    def test_bounding_box(self):
        bbox = self.qs[0].geom.extent
        response = self.client.get(self.url, {"bbox": ",".join(map(str, bbox))})
        self.assertEqual(len(response.data["features"]), 1)

    def test_spatial_lookup(self):
        centroid = self.qs[0].geom.centroid.geojson
        response = self.client.get(self.url, {"intersects": centroid})
        self.assertEqual(len(response.data["features"]), 1)

    def test_spatial_lookup_notfound(self):
        response = self.client.get(self.url, {"intersects": "POINT(0 0)"})
        self.assertEqual(len(response.data["features"]), 0)

    def test_geojson(self):
        response = self.client.get(self.url, {"format": "geojson"})
        self.assertIsInstance(response.accepted_renderer, GeoJSONRenderer)
        response = self.client.get(self.url, HTTP_ACCEPT=GeoJSONRenderer.media_type)
        self.assertIsInstance(response.accepted_renderer, GeoJSONRenderer)
        for geom, obj in zip(self._parse_collection(response), self.qs):
            self.assertTrue(geom.equals_exact(obj.geom, 0.0001))

    def test_geojson_exception(self):
        # Resetting renderers on exception with ResponseExceptionMixin throws
        # NotAcceptable.
        response = self.client.get(
            self.url,
            {"intersects": "POINT(null+null)"},
            HTTP_ACCEPT=GeoJSONRenderer.media_type,
        )
        self.assertTrue(response.status_code, 400)
        self.assertTrue(response.accepted_renderer, GeoJSONRenderer)

    def test_simplify(self):
        srid = 3857
        for format in "json", "geojson":
            response = self.client.get(
                self.url, {"simplify": 10000, "srs": srid, "format": format}
            )
            for geom, obj in zip(self._parse_collection(response, srid), self.qs):
                orig = obj.geom.transform(srid, clone=True)
                self.assertNotEqual(geom, orig)
                self.assertLess(geom.num_coords, orig.num_coords)
        self.assertContains(response, "EPSG::%d" % srid)


class GeoListCreateAPIView(TestCase):
    def setUp(self):
        self.view = generics.GeoListCreateAPIView.as_view(
            queryset=Location.objects.all()
        )
        Location.create()
        self.qs = Location.objects.all()

    def test_post(self):
        fs = LocationFeatureSerializer(self.qs, many=True)
        request = factory.post("/", fs.data, format="json")
        with self.assertNumQueries(1):
            response = self.view(request).render()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = self.qs.get(pk=2)
        self.assertEqual(created.name, "Vancouver")
        self.assertEqual(created.geom, fs.instance[0].geom)


class PaginatedGeoListViewTestCase(TestCase):
    def setUp(self):
        for i in range(20):
            Location.create()
        self.qs = Location.objects.all()

    def _test_paginate(self, params, **kwargs):
        response = self.client.get("/locations/", params, **kwargs)
        data = response.json()
        self.assertEqual(
            len(data["features"]), PaginatedGeoListView.pagination_class.page_size
        )
        self.assertEqual(data["count"], len(self.qs))
        for k in "previous", "next":
            self.assertIn(k, data)
        return data

    def test_paginate(self):
        self._test_paginate({"page": 2})

    def test_paginate_geojson(self):
        data = self._test_paginate({"page": 1}, HTTP_ACCEPT=GeoJSONRenderer.media_type)
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertIn("crs", data)


class RasterListViewTestCase(RasterStoreTestBase):
    def test_list_apidoc(self):
        response = self.client.get("/rasters/", {"format": "api"})
        self.assertRegexpMatches(
            response.content.decode("utf-8"), "image.+?http://.*\.tif"
        )
        point = self.object.geom.centroid
        response = self.client.get("/rasters/", {"format": "api", "g": point.wkt})
        self.assertEqual(response.data[0]["image"], 12)

    def test_list_json(self):
        d = self.client.get("/rasters/").json()
        self.assertRegexpMatches(d[0]["image"], "^http://.*\.tif$")

    def test_list_json_array(self):
        with Raster(self.object.image.path) as r:
            imdata = r.array().tolist()
            g = r.envelope.polygon.__geo_interface__
            sref_wkt = str(r.sref)
            point = r.envelope.polygon.Centroid()
        d = self.client.get("/rasters/", {"g": json.dumps(g)}).json()
        expected = [{"image": imdata, "geom": g, "srs": sref_wkt}]
        self.assertEqual(*map(len, (d, expected)))
        self.assertDictContainsSubset(expected[0], d[0])
        # Test point geometry type.
        d = self.client.get("/rasters/", {"g": point.ExportToJson()}).json()
        idx = int(len(imdata) / 2)
        expected[0]["image"] = imdata[idx][idx]
        self.assertDictContainsSubset(expected[0], d[0])

    def test_list_zip(self):
        response = self.client.get("/rasters/", {"format": "img.zip"})
        self.assertTrue(response.streaming)
        self.assertEqual(response["content-disposition"].split("=")[1], "data.img.zip")
        bio = io.BytesIO(b"".join(response.streaming_content))
        zf = zipfile.ZipFile(bio)
        self.assertEqual(len(zf.filelist), len(self.qs))

    def test_options(self):
        # Client could inadvertently make options request with wrong accept header.
        response = self.client.options(
            "/rasters/", HTTP_ACCEPT=GeoTIFFZipRenderer.media_type
        )
        self.assertEqual(response.status_code, NotAcceptable.status_code)
        response = self.client.options("/rasters/")
        self.assertEqual(response.status_code, 200)

    def test_not_acceptable(self):
        response = self.client.get("/rasters/", HTTP_ACCEPT="image/tiff")
        self.assertEqual(response.status_code, NotAcceptable.status_code)
        self.assertEqual(response["content-type"], "application/json")

    def test_spatial_lookup(self):
        corner = self.object.geom.extent[:2]
        point = self.object.geom.centroid
        point.x = corner[0] - 10
        response = self.client.get("/rasters/", {"intersects": point.wkt})
        self.assertEqual(len(response.data), 0)

    def test_404(self):
        response = self.client.get("/rasters/-9999/", {"format": "img.zip"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["content-type"], "text/html")
        response = self.client.get("/rasters/-9999/")
        self.assertEqual(response["content-type"], "application/json")
