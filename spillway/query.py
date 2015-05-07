from django.contrib.gis import geos
from django.contrib.gis.db.models import query
from django.db import connection

def filter_geometry(queryset, **filters):
    """Helper function for spatial lookups filters.

    Provide spatial lookup types as keywords without underscores instead of the
    usual "geometryfield__lookuptype" format.
    """
    fieldname = geo_field(queryset).name
    query = {'%s__%s' % (fieldname, k): v for k, v in filters.items()}
    return queryset.filter(**query)

def geo_field(queryset):
    # Try Django 1.8 syntax first, then fall back to 1.7 and below.
    try:
        return queryset._geo_field()
    except AttributeError:
        return queryset.query._geo_field()

def get_srid(queryset):
    """Returns the GeoQuerySet spatial reference identifier."""
    try:
        # Django 1.8
        srid = queryset.query.get_context('transformed_srid')
    except AttributeError:
        # Django<=1.7
        srid = queryset.query.transformed_srid
    return srid or queryset.geo_field.srid


# Many GeoQuerySet methods cannot be chained as expected and extending
# GeoQuerySet to work properly with serialization calls like
# .simplify(100).svg() will require patching
# django.contrib.gis.db.models.query. Work around this with a custom
# GeoQuerySet for now.
class GeoQuerySet(query.GeoQuerySet):
    """Extends the default GeoQuerySet with some unimplemented PostGIS
    functionality.
    """
    _scale = '%s(%%s, %%s, %%s)' % connection.ops.scale
    # Geometry outputs
    _formats = {'geojson': '%s(%%s, %%s)' % connection.ops.geojson,
                'kml': '%s(%%s, %%s)' % connection.ops.kml,
                'svg': '%s(%%s, 0, %%s)' % connection.ops.svg}

    def _as_format(self, sql, format=None, precision=8):
        val = self._formats.get(format, self._formats['geojson'])
        return self.extra(select={format: val % (sql, precision)})

    def _transform(self, colname, srid=None):
        if srid:
            self.transform(srid)
        return ('%s(%s, %s)' % (connection.ops.transform, colname, srid)
                if srid else colname)

    def _simplify(self, colname, tolerance=0.0):
        # connection.ops does not have simplify available for PostGIS.
        return ('ST_Simplify(%s, %s)' % (colname, tolerance)
                if tolerance else colname)

    def extent(self, srid=None):
        """Returns the GeoQuerySet extent as a 4-tuple.

        The method chaining approach of
        geoqset.objects.transform(srid).extent() returns the extent in the
        original coordinate system, this method allows for transformation.

        Keyword args:
        srid -- EPSG id for for transforming the output geometry.
        """
        if not srid and not connection.ops.spatialite:
            return super(GeoQuerySet, self).extent()
        transform = self._transform(self.geo_field.column, srid)
        # Spatialite extent() is supported post-1.7.
        if connection.ops.spatialite:
            ext = {'extent': 'AsText(%s(%s))' % ('Extent', transform)}
        else:
            ext = {'extent': '%s(%s)' % (connection.ops.extent, transform)}
        try:
            # The bare order_by() is needed to remove the default sort field
            # which is not present in this aggregation.
            extent = (self.extra(select=ext)
                          .values_list('extent', flat=True)
                          .order_by()[0])
        except IndexError:
            return ()
        try:
            try:
                # Django<=1.7
                return connection.ops.convert_extent(extent)
            except TypeError:
                # Django 1.8
                return connection.ops.convert_extent(extent, get_srid(self))
        except NotImplementedError:
            return geos.GEOSGeometry(extent, srid).extent

    def filter_geometry(self, **kwargs):
        """Convenience method for spatial lookup filters."""
        return filter_geometry(self, **kwargs)

    @property
    def geo_field(self):
        """Returns model geometry field."""
        return geo_field(self)

    def has_format(self, format):
        return format in self._formats

    def scale(self, x, y, z=0.0, tolerance=0.0, precision=8, srid=None,
              format=None, **kwargs):
        """Returns a GeoQuerySet with scaled and optionally reprojected and
        simplified geometries, serialized to a supported format.
        """
        if not any((tolerance, srid, format)):
            return super(GeoQuerySet, self).scale(x, y, z, **kwargs)
        transform = self._transform(self.geo_field.column, srid)
        scale = self._scale % (transform, x, y)
        simplify = self._simplify(scale, tolerance)
        return self._as_format(simplify, format, precision)

    def simplify(self, tolerance=0.0, srid=None, format=None, precision=8):
        """Returns a GeoQuerySet with simplified geometries serialized to
        a supported geometry format.
        """
        # Transform first, then simplify.
        transform = self._transform(self.geo_field.column, srid)
        simplify = self._simplify(transform, tolerance)
        if format:
            return self._as_format(simplify, format, precision)
        # TODO: EWKB bug is fixed in spatialite 4.2+ so this can be removed.
        if connection.ops.spatialite:
            # Spatialite returns additional precision when converting to wkt,
            # so avoid the call unless we are simplifying geometries.
            if not (tolerance or srid):
                return self
            simplify = 'AsEWKT(%s)' % simplify
        return self.extra(select={self.geo_field.name: simplify})
