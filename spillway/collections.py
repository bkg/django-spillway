from __future__ import absolute_import
import collections

from greenwich.srs import SpatialReference

from spillway.compat import json, JSONEncoder

def as_feature(data):
    """Returns a Feature or FeatureCollection.

    Arguments:
    data -- Sequence or Mapping of Feature-like or FeatureCollection-like data
    """
    if not isinstance(data, (Feature, FeatureCollection)):
        if is_featurelike(data):
            data = Feature(**data)
        elif has_features(data):
            data = FeatureCollection(**data)
        elif isinstance(data, collections.Sequence):
            data = FeatureCollection(features=data)
        elif has_layer(data):
            data = LayerCollection(data)
        elif has_coordinates(data):
            data = Feature(geometry=data)
        elif isinstance(data, collections.Mapping) and not data:
            data = Feature()
    return data

def has_coordinates(geometry):
    """Returns true for a Geometry-like structure."""
    try:
        return 'coordinates' in geometry
    except (AttributeError, TypeError):
        return False

def has_features(fcollection):
    """Returns true for a FeatureCollection-like structure."""
    try:
        return 'features' in fcollection
    except (AttributeError, TypeError):
        return False

def is_featurelike(feature):
    """Returns true for a Feature-like structure."""
    try:
        return 'geometry' in feature and 'properties' in feature
    except (AttributeError, TypeError):
        return False

def has_layer(fcollection):
    """Returns true for a multi-layer dict of FeatureCollections."""
    for val in fcollection.itervalues():
        if has_features(val):
            return True
    return False


class LinkedCRS(dict):
    def __init__(self, srid=4326, iterable=(), **kwargs):
        self['type'] = 'link'
        if isinstance(srid, int):
            self['properties'] = {
                'href': 'http://spatialreference.org/ref/epsg/%s/proj4/' % srid,
                'type': 'proj4'
            }
        else:
            iterable = iterable or srid
        self.update(iterable, **kwargs)


class NamedCRS(dict):
    def __init__(self, srid=4326, iterable=(), **kwargs):
        self['type'] = 'name'
        if isinstance(srid, int):
            self['properties'] = {'name': 'urn:ogc:def:crs:EPSG::%s' % srid}
        else:
            iterable = iterable or srid
        self.update(iterable, **kwargs)


class AbstractFeature(dict):
    """Abstract Feature class"""

    @property
    def __geo_interface__(self):
        return self

    def __str__(self):
        return self.geojson

    def _dumps(self):
        return json.dumps(self, cls=JSONEncoder)

    @property
    def geojson(self):
        raise NotImplementedError

    def is_serialized(self, key):
        return isinstance(self[key], basestring)

    def copy(self):
        return self.__class__(**super(AbstractFeature, self).copy())

    @property
    def srs(self):
        try:
            return SpatialReference(self['crs']['properties']['name'])
        except KeyError:
            return None


class Feature(AbstractFeature):
    """GeoJSON Feature dict."""

    def __init__(self, id=None, geometry=None, properties=None,
                 crs=None, iterable=(), **kwargs):
        super(Feature, self).__init__()
        self['type'] = self.__class__.__name__
        self['geometry'] = geometry or {}
        self['properties'] = properties or kwargs or {}
        if id:
            self['id'] = id
        if crs:
            self['crs'] = NamedCRS(crs)
        self.update(iterable)

    @property
    def geojson(self):
        if not self.is_serialized('geometry'):
            return self._dumps()
        geom = self['geometry'] or '{}'
        keys = self.viewkeys() - {'geometry'}
        props = json.dumps({k: self[k] for k in keys}, cls=JSONEncoder)[1:-1]
        return '{"geometry": %s, %s}' % (str(geom), props)


class FeatureCollection(AbstractFeature):
    """GeoJSON FeatureCollection dict."""

    def __init__(self, features=None, crs=None, iterable=(), **kwargs):
        super(FeatureCollection, self).__init__()
        self['type'] = self.__class__.__name__
        if crs:
            self['crs'] = NamedCRS(crs)
        if features and not isinstance(features[0], Feature):
            self['features'] = [Feature(**feat) for feat in features]
        else:
            self['features'] = features or []
        self.update(iterable, **kwargs)

    @property
    def geojson(self):
        if not self.has_serialized_geom:
            return self._dumps()
        features = ','.join(map(str, self['features']))
        keys = self.viewkeys() - {'features'}
        collection = '%s, "features": [' % json.dumps(
            {k: self[k] for k in keys}, cls=JSONEncoder)[:-1]
        return ''.join([collection, features, ']}'])

    @property
    def has_serialized_geom(self):
        return any(feat.is_serialized('geometry') for feat in self['features'])


class LayerCollection(AbstractFeature):
    """Layer dict of FeatureCollections."""

    def __init__(self, iterable=(), **kwargs):
        super(LayerCollection, self).__init__()
        self.update(iterable, **kwargs)
        for key, val in self.iteritems():
            if not isinstance(val, FeatureCollection):
                self[key] = FeatureCollection(**val)

    @property
    def geojson(self):
        layers = ','.join(['"%s": %s' % (k, v.geojson)
                           for k, v in self.iteritems()])
        return '{%s}' % layers
