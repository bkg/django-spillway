from django.test import TestCase
from rest_framework.compat import django_filters
from rest_framework.test import APIRequestFactory

from spillway import filters, generics
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
        self.assertEqual(len(response.data), 1)

    def test_bounding_box(self):
        bbox = self.qs[0].geom.extent
        params = {'bbox': ','.join(map(str, bbox))}
        request = factory.get('/', params)
        response = self.view(request)
        self.assertEqual(len(response.data), 1)

    def test_spatial_lookup_notfound(self):
        params = {'intersects': 'POINT(0 0)'}
        request = factory.get('/', params)
        response = self.view(request)
        self.assertEqual(len(response.data), 0)

    def test_geoqueryset(self):
        request = factory.get('/', {'simplify': 0.1, 'srs': 3857})
        response = self.view(request)
        self.assertEqual(len(response.data), len(self.qs))
