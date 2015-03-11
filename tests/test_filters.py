import json

from django.contrib.gis import geos
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from spillway import generics
from .models import Location

factory = APIRequestFactory()


class FilterTestCase(TestCase):
    def setUp(self):
        records = [{'name': 'Banff', 'coordinates': [-115.554, 51.179]},
                   {'name': 'Jasper', 'coordinates': [-118.081, 52.875]}]
        self.view = generics.GeoListView.as_view(model=Location)
        for record in records:
            obj = Location.add_buffer(record.pop('coordinates'), 0.5, **record)
        self.qs = Location.objects.all()

    def test_spatial_lookup(self):
        centroid = Location.objects.centroid()[0].centroid.geojson
        params = {'intersects': centroid}
        request = factory.get('/', params)
        response = self.view(request)
        self.assertEqual(len(response.data['features']), 1)

    def test_bounding_box(self):
        bbox = self.qs[0].geom.extent
        params = {'bbox': ','.join(map(str, bbox))}
        request = factory.get('/', params)
        response = self.view(request)
        self.assertEqual(len(response.data['features']), 1)

    def test_spatial_lookup_notfound(self):
        params = {'intersects': 'POINT(0 0)'}
        request = factory.get('/', params)
        response = self.view(request)
        self.assertEqual(len(response.data['features']), 0)

    def test_geoqueryset(self):
        srid = 3857
        request = factory.get('/', {'simplify': 10000, 'srs': srid})
        response = self.view(request).render()
        simplified = json.loads(response.content)
        self.assertEqual(len(simplified['features']), len(self.qs))
        for feature, obj in zip(simplified['features'], self.qs):
            geom = geos.GEOSGeometry(json.dumps(feature['geometry']), srid)
            orig = obj.geom.transform(srid, clone=True)
            self.assertNotEqual(geom, orig)
            self.assertNotEqual(geom.num_coords, orig.num_coords)
        self.assertContains(response, 'EPSG::%d' % srid)
