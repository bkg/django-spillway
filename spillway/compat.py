from django.core.exceptions import ImproperlyConfigured
from rest_framework.utils import encoders

try:
    # Django 1.8+
    from django.contrib.gis.db.models.lookups import gis_lookups as ALL_TERMS
except ImportError:
    # Django<=1.7
    from django.contrib.gis.db.models.sql.query import ALL_TERMS

try:
    import simplejson as json
except ImportError:
    import json
    JSONEncoder = encoders.JSONEncoder
else:
    # Workaround to support simplejson 2.2+, see
    # https://github.com/simplejson/simplejson/issues/37
    class JSONEncoder(json.JSONEncoder):
        default = encoders.JSONEncoder().default

try:
    import mapnik
except ImportError:
    class Mapnik(object):
        def __getattr__(self, attr):
            raise ImproperlyConfigured('Mapnik must be installed')

    mapnik = Mapnik()
