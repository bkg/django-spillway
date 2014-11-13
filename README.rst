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

    from spillway import generics
    from myapp.models import County

    urlpatterns = patterns('',
        url(r'^counties/$',
            generics.GeoListView.as_view(model=County),
            name='county-list'),
    )


Retrieve all counties as GeoJSON::

    curl -H 'Accept: application/vnd.geo+json' 127.0.0.1:8000/counties/

Simplify and reproject the geometries to another coordinate system.::

    curl -H 'Accept: application/vnd.geo+json' '127.0.0.1:8000/counties/?srs=3857&simplify=100'

Any `spatial lookup
<https://docs.djangoproject.com/en/dev/ref/contrib/gis/geoquerysets/#spatial-lookups>`_
supported by the backend is available to search on. For instance, find the county which
intersects a particular point::

    curl -g 'localhost:8000/counties?intersects={"type":"Point","coordinates":[-120,38]}'
