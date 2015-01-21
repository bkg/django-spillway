Django-Spillway
===============

.. image:: https://travis-ci.org/bkg/django-spillway.svg?branch=master
    :target: https://travis-ci.org/bkg/django-spillway
.. image:: https://img.shields.io/coveralls/bkg/django-spillway.svg
    :target: https://coveralls.io/r/bkg/django-spillway?branch=master

`Django <http://www.djangoproject.com/>`_ and `Django REST Framework <http://www.django-rest-framework.org/>`_ integration of raster and feature based geodata.

Spillway builds on the immensely marvelous Django REST Framework by providing
facilities for the handling of geospatial formats such as GeoTIFF, GeoJSON, and
KML/KMZ.

Specific attention has been paid to speedy serialization of geometries from
spatial backends which avoids the cost of unneccessary re-serialization in
Python.

Basic Usage
-----------

Add vector response formats such as GeoJSON, KML/KMZ, and SVG to your API.

.. code-block:: python

    # models.py
    from django.contrib.gis.db import models
    from spillway.models import GeoManager

    class Location(models.Model):
        slug = models.SlugField()
        geom = models.GeometryField()
        objects = GeoManager()

    # urls.py
    from django.conf.urls import patterns, url
    from spillway import generics
    from .models import Location

    urlpatterns = patterns('',
        url(r'^locations/(?P<slug[\w-]+)/$',
            generics.GeoDetailView.as_view(model=Location),
            name='location'),
        url(r'^locations/$',
            generics.GeoListView.as_view(model=Location),
            name='location-list'),
    )

Retrieve all locations as GeoJSON::

    curl -H 'Accept: application/vnd.geo+json' 127.0.0.1:8000/locations/

Simplify and reproject the geometries to another coordinate system::

    curl -H 'Accept: application/vnd.geo+json' '127.0.0.1:8000/locations/?srs=3857&simplify=100'

Any `spatial lookup
<https://docs.djangoproject.com/en/dev/ref/contrib/gis/geoquerysets/#spatial-lookups>`_
supported by the backend is available to search on. For instance, find the location which
intersects a particular point::

    curl -g '127.0.0.1:8000/locations/?intersects={"type":"Point","coordinates":[-120,38]}'

Raster data support is provided as well.

.. code-block:: python

    from django.conf.urls import patterns, url
    from spillway import generics
    from .models import RasterStore

    urlpatterns = patterns('',
        url(r'^rstores/(?P<slug>[\w-]+)/$',
            generics.RasterDetailView.as_view(model=RasterStore),
            name='rasterstore'),
        url(r'^rstores/$',
            generics.RasterListView.as_view(model=RasterStore),
            name='rasterstore-list'),
    )

Return JSON containing a 2D array of pixel values for a given bounding box::

    curl 'http://127.0.0.1:8000/rstores/tasmax/?bbox=-107.74,37.39,-106.95,38.40'

One can crop raster images with a geometry and return a .zip archive of the
results::

    curl  -H 'Accept: application/zip' 'http://127.0.0.1:8000/rstores/?g=-107.74,37.39,-106.95,38.40'
