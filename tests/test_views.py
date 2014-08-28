import json

from rest_framework.test import APIRequestFactory, APITestCase

from spillway import views
from .models import Location


class TileViewTestCase(APITestCase):
    def setUp(self):
        self.view = views.TileView.as_view(model=Location)
        self.geometry = {'type': 'Polygon',
                         'coordinates': [[ [14.14, 50.21],
                                           [14.39, 49.76],
                                           [14.89, 50.20],
                                           [14.14, 50.21] ]]}
        Location.create(name='Prague', geom=self.geometry)

    def test_response(self):
        response = self.client.get('/tiles/10/553/347/')
        d = json.loads(response.content)
        # This particular geometry clipped to a tile should have +1 coords.
        self.assertEqual(len(d['features'][0]['geometry']['coordinates'][0]),
                         len(self.geometry['coordinates'][0]) + 1)
