import json
import math
from decimal import Decimal, getcontext

from django.test import TestCase
from rest_framework.compat import django_filters
from rest_framework.test import APIRequestFactory
from django.contrib.gis.geos import Polygon

from spillway import generics
from .models import Location

factory = APIRequestFactory()
fcollection = {
  'type': 'FeatureCollection',
  'features': [{
      'type': 'Feature',
      'properties': {
        'name': 'Banff'
      },
      'geometry': {
        'type': 'Polygon',
        'coordinates': [[
            [-116.685, 50.903],
            [-115.631, 52.001],
            [-114.834, 50.495],
            [-116.685, 50.903]
        ]]
      }
    }, {
      'type': 'Feature',
      'properties': {
        'name': 'Jasper'
      },
      'geometry': {
        'type': 'Polygon',
        'coordinates': [[
            [-118.822, 53.612],
            [-117.097, 52.819],
            [-119.009, 52.301],
            [-118.822, 53.612]

        ]]
      }
    }
  ]
}

def create_polygon_circle(middle_x=-100, middle_y=30, vertices=40, radius=2):
    coords = ()
    getcontext().prec = 4
    for i in range(0, vertices):
        rad = Decimal(i)/Decimal(vertices) * Decimal(math.pi)
        x = math.sin(rad) * radius + middle_x
        y = math.cos(rad) * radius + middle_y
        if i == 0:
            last = (x, y)
        coords = coords + ((x, y),)
    coords = coords + (last, )
    return Polygon(coords)


class FilterTestCase(TestCase):
    def setUp(self):
        self.view = generics.GeoListView.as_view(model=Location)
        for feature in fcollection['features']:
            attrs = dict(geom=feature['geometry'], **feature['properties'])
            obj = Location.create(**attrs)
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
        request = factory.get('/', {'simplify': 0.1, 'srs': 3857})
        response = self.view(request).render()
        self.assertEqual(len(response.data['features']), len(self.qs))
        fc = json.loads(response.content)
        feat = json.loads(self.qs[0].geom.geojson)
        self.assertNotEqual(fc['features'][0], feat)
        self.assertIn('EPSG::3857', response.content)


class TestSimplify(TestCase):
    def setUp(self):
        self.view = generics.GeoListView.as_view(model=Location)
        loc = Location()
        loc.geom, loc.name = create_polygon_circle(), 'Falk'
        loc.save()

    def test_simplify(self):
        request = factory.get('/', {'simplify': .01})
        response = self.view(request).render()
        num_coords = len(
            json.loads(
                response.content)[
                    'features'][0]['geometry']['coordinates'][0])
        qs = Location.objects.filter(name='Falk')
        self.assertLess(num_coords, qs[0].geom.num_coords)

