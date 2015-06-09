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
    from spillway.query import GeoQuerySet

    class Location(models.Model):
        slug = models.SlugField()
        geom = models.GeometryField()
        objects = GeoQuerySet.as_manager()

    # urls.py
    from django.conf.urls import patterns, url
    from spillway import generics
    from .models import Location

    urlpatterns = patterns('',
        url(r'^locations/(?P<slug[\w-]+)/$',
            generics.GeoDetailView.as_view(queryset=Location.objects.all()),
            name='location'),
        url(r'^locations/$',
            generics.GeoListView.as_view(queryset=Location.objects.all()),
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
    from spillway.generics import RasterDetailView, RasterListView
    from .models import RasterStore

    urlpatterns = patterns('',
        url(r'^rstores/(?P<slug>[\w-]+)/$',
            RasterDetailView.as_view(queryset=RasterStore.objects.all()),
            name='rasterstore'),
        url(r'^rstores/$',
            RasterListView.as_view(queryset=RasterStore.objects.all()),
            name='rasterstore-list'),
    )

Return JSON containing a 2D array of pixel values for a given bounding box::

    curl 'http://127.0.0.1:8000/rstores/tasmax/?bbox=-107.74,37.39,-106.95,38.40'

One can crop raster images with a geometry and return a .zip archive of the
results::

    curl  -H 'Accept: application/zip' 'http://127.0.0.1:8000/rstores/?g=-107.74,37.39,-106.95,38.40'


Generic Views
-------------
Spillway extends REST framework generic views with GeoJSON and KML/KMZ
renderers for geographic data. This includes pagination of features and all
available spatial lookups/filters for the spatial backend in use.


Renderers
---------
So far there are renderers for common raster and vector data formats, namely
zipped GeoTIFF, JPEG, PNG, and Erdas Imagine, plus GeoJSON, KML/KMZ, and SVG.


Tests
-----
Create a `virtualenv <https://virtualenv.pypa.io/en/latest/>`_ with
`virtualenvwrapper <https://virtualenvwrapper.readthedocs.org/en/latest/>`_,
install dependencies, and run the tests. Running tests with SpatiaLite requires
a build of pysqlite with extension loading enabled.

.. code-block:: shell

    mkvirtualenv spillway
    pip install --global-option=build_ext --global-option='-USQLITE_OMIT_LOAD_EXTENSION' pysqlite
    pip install -r requirements.txt
    make check
