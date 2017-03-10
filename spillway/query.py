import os
import tempfile
import zipfile

from django.core import exceptions
from django.contrib.gis import geos
from django.contrib.gis.db.models import query
from django.db import connection, models
from django.utils.functional import cached_property
import greenwich
from greenwich.io import MemFileIO
import numpy as np

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

    def _transform(self, srid=None):
        args, geo_field = self._spatial_setup('transform')
        if not srid:
            return args['geo_col']
        try:
            # Django 1.8
            self.query.add_context('transformed_srid', srid)
        except AttributeError:
            # Django<=1.7
            self.query.transformed_srid = srid
        return '%s(%s, %s)' % (args['function'], args['geo_col'], srid)

    def _trans_scale(self, colname, deltax, deltay, xfactor, yfactor):
        if connection.ops.spatialite:
            sql = 'ScaleCoords(ShiftCoords(%s, %.12f, %.12f), %.12f, %.12f)'
        else:
            sql = 'ST_TransScale(%s, %.12f, %.12f, %.12f, %.12f)'
        return sql % (colname, deltax, deltay, xfactor, yfactor)

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
        transform = self._transform(srid)
        # Spatialite extent() is supported post-1.7.
        if connection.ops.spatialite:
            ext = {'extent': 'AsText(%s(%s))' % ('Extent', transform)}
        else:
            ext = {'extent': '%s(%s)' % (connection.ops.extent, transform)}
        # The bare order_by() is needed to remove the default sort field which
        # is not present in this aggregation. Empty querysets will return
        # [None] here.
        extent = (self.extra(select=ext)
                      .values_list('extent', flat=True)
                      .order_by()[0])
        if not extent:
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

    def pbf(self, bbox, geo_col=None, scale=4096):
        """Returns tranlated and scaled geometries suitable for Mapbox vector
        tiles.
        """
        col = geo_col or self._transform()
        w, s, e, n = bbox.extent
        trans = self._trans_scale(col, -w, -s,
                                  scale / (e - w),
                                  scale / (n - s))
        return self.extra(select={'pbf': 'ST_AsText(%s)' % trans})

    def scale(self, x, y, z=0.0, tolerance=0.0, precision=8, srid=None,
              format=None, **kwargs):
        """Returns a GeoQuerySet with scaled and optionally reprojected and
        simplified geometries, serialized to a supported format.
        """
        if not any((tolerance, srid, format)):
            return super(GeoQuerySet, self).scale(x, y, z, **kwargs)
        transform = self._transform(srid)
        scale = self._scale % (transform, x, y)
        simplify = self._simplify(scale, tolerance)
        return self._as_format(simplify, format, precision)

    def simplify(self, tolerance=0.0, srid=None, format=None, precision=8):
        """Returns a GeoQuerySet with simplified geometries serialized to
        a supported geometry format.
        """
        # Transform first, then simplify.
        transform = self._transform(srid)
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

    def tile(self, bbox, tolerance=0.0, format=None, clip=False):
        """Returns a GeoQuerySet intersecting a tile boundary.

        Arguments:
        bbox -- tile extent as geometry
        Keyword args:
        tolerance -- geometry simplification tolerance
        format -- vector tile format as str
        clip -- clip geometries to tile boundary as boolean
        """
        clone = filter_geometry(self, intersects=getattr(bbox, 'geos', bbox))
        # Tile grid uses 3857, but coordinates should be in 4326 commonly.
        tile_srid = 3857
        coord_srid = bbox.srid
        transform = clone._transform()
        if clip:
            ewkt = ('GeomFromEWKT' if connection.ops.spatialite else
                    'ST_GeomFromEWKT')
            transform = "ST_Intersection(%s, %s('%s'))" % (
                transform, ewkt, bbox.ewkt)
        if clone.geo_field.srid != tile_srid:
            transform = 'ST_Transform(%s, %s)' % (transform, tile_srid)
        simplify = clone._simplify(transform, tolerance)
        latlng = 'ST_Transform(%s, %s)' % (simplify, coord_srid)
        if format == 'pbf':
            return clone.pbf(bbox, geo_col=latlng)
        return clone._as_format(latlng, format)


class RasterQuerySet(GeoQuerySet):
    def arrays(self, field_name=None):
        """Returns a list of ndarrays.

        Keyword args:
        field_name -- raster field name as str
        """
        fieldname = field_name or self.raster_field.name
        arrays = []
        for obj in self:
            arr = getattr(obj, fieldname)
            if isinstance(arr, np.ndarray):
                arrays.append(arr)
            else:
                arrays.append(obj.array())
        return arrays

    def aggregate_periods(self, periods):
        """Returns list of ndarrays averaged to a given number of periods.

        Arguments:
        periods -- desired number of periods as int
        """
        try:
            fieldname = self.raster_field.name
        except TypeError:
            raise exceptions.FieldDoesNotExist('Raster field not found')
        arrays = self.arrays(fieldname)
        arr = arrays[0]
        fill = getattr(arr, 'fill_value', None)
        if getattr(arr, 'ndim', 0) > 2:
            arrays = np.vstack(arrays)
        if len(arrays) > 1:
            marr = np.ma.array(arrays, fill_value=fill, copy=False)
        else:
            marr = arrays[0]
        # Try to reshape using equal sizes first and fall back to unequal
        # splits.
        try:
            means = marr.reshape((periods, -1)).mean(axis=1)
        except ValueError:
            means = [a.mean() for a in np.array_split(marr, periods)]
        obj = self[0]
        setattr(obj, fieldname, means)
        return [obj]

    def get(self, *args, **kwargs):
        # Need special handling of model instances with modified attributes,
        # otherwise they will be lost.
        if self._result_cache is not None:
            for obj in self._result_cache:
                for attr, val in kwargs.items():
                    if getattr(obj, attr) == val:
                        return obj
            raise self.model.DoesNotExist(
                '%s matching query does not exist.' %
                self.model._meta.object_name)
        return super(RasterQuerySet, self).get(*args, **kwargs)

    @cached_property
    def raster_field(self):
        """Returns the raster FileField instance on the model."""
        for field in self.model._meta.fields:
            if isinstance(field, models.FileField):
                return field
        return False

    def summarize(self, geom, stat=None):
        """Returns a new RasterQuerySet with subsetted/summarized ndarrays.

        Arguments:
        geom -- geometry for masking or spatial subsetting
        Keyword args:
        stat -- numpy supported summary stat as str (min/max/mean/etc)
        """
        if not hasattr(geom, 'num_coords'):
            raise TypeError('Need OGR or GEOS geometry, %s found' % type(geom))
        clone = self._clone()
        for obj in clone:
            arr = obj.array(geom)
            if arr is not None:
                if stat:
                    axis = None
                    if arr.ndim > 2:
                        axis = 1
                        arr = arr.reshape(arr.shape[0], -1)
                    arr = getattr(np.ma, stat)(arr, axis)
                if arr.size == 1:
                    arr = arr.item()
            obj.image = arr
        return clone

    def warp(self, srid=None, format=None, geom=None):
        """Returns a new RasterQuerySet with possibly warped/converted rasters.

        Keyword args:
        format -- raster file extension format as str
        geom -- geometry for masking or spatial subsetting
        srid -- spatial reference identifier as int for warping to
        """
        clone = self._clone()
        for obj in clone:
            obj.convert(format, geom)
            if srid:
                f = obj.image.file
                if isinstance(f, MemFileIO):
                    r = greenwich.Raster(f.name)
                else:
                    r = obj.raster()
                memio = MemFileIO(delete=False)
                dswarp = r.warp(srid, memio)
                obj.image.file = memio
                dswarp.close()
                r.close()
        return clone
