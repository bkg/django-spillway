from django.core.exceptions import ImproperlyConfigured

try:
    import simplejson as json
except ImportError:
    import json

try:
    import mapnik
except ImportError:
    class Mapnik(object):
        def __getattr__(self, attr):
            raise ImproperlyConfigured('Mapnik must be installed')
    mapnik = Mapnik()
