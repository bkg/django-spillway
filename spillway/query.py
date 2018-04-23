import os
import math
import tempfile
import zipfile

from django.core import exceptions
from django.contrib.gis import geos
from django.contrib.gis.db.models import query, Extent
import django.contrib.gis.db.models.functions as geofn
from django.db import connection, models
from django.utils.functional import cached_property
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
    """Returns the GeometryField for a django or spillway GeoQuerySet."""
    try:
        return queryset.geo_field
    except AttributeError:
        return queryset._geo_field()

def get_srid(queryset):
    """Returns the GeoQuerySet spatial reference identifier."""
    srid = queryset.query.get_context('transformed_srid')
    return srid or geo_field(queryset).srid

def aggregate1d(arr, stat):
    """Returns a 1D array with higher dimensions aggregated using stat fn.

    Arguments:
    arr -- ndarray
    stat -- np or np.ma function as str to call
    """
    axis = None
    if arr.ndim > 2:
        axis = 1
        arr = arr.reshape(arr.shape[0], -1)
    module = np.ma if hasattr(arr, 'mask') else np
    arr = getattr(module, stat)(arr, axis)
    return arr


class AsText(geofn.GeoFunc):
    output_field_class = models.TextField


class Simplify(geofn.GeoFunc):
    arity = 2


class SimplifyPreserveTopology(geofn.GeoFunc):
    arity = 2


class TransScale(geofn.GeoFunc):
    pass


class GeoQuerySet(query.GeoQuerySet):
    """Extends the default GeoQuerySet with some unimplemented PostGIS
    functionality.
    """
    # Geometry simplification tolerances based on tile width (m) per zoom
    # level, see http://wiki.openstreetmap.org/wiki/Zoom_levels
    tilewidths = [6378137 * 2 * math.pi / (2 ** (zoom + 8))
                  for zoom in range(20)]

    def _trans_scale(self, colname, deltax, deltay, xfactor, yfactor):
        if connection.ops.spatialite:
            return geofn.Scale(geofn.Translate(colname, deltax, deltay), xfactor, yfactor)
        else:
            return TransScale(colname, deltax, deltay, xfactor, yfactor)

    def extent(self, srid=None):
        """Returns the GeoQuerySet extent as a 4-tuple.

        Keyword args:
        srid -- EPSG id for for transforming the output geometry.
        """
        fieldname = self.geo_field.name
        ext = Extent(fieldname)
        key = '%s__extent' % fieldname
        clone = self.all()
        qs = clone.transform(srid) if srid else clone
        return qs.aggregate(ext)[key]

    def filter_geometry(self, **kwargs):
        """Convenience method for spatial lookup filters."""
        return filter_geometry(self, **kwargs)

    @property
    def geo_field(self):
        """Returns model geometry field."""
        return self._geo_field()

    def pbf(self, bbox, geo_col=None, scale=4096):
        """Returns tranlated and scaled geometries suitable for Mapbox vector
        tiles.
        """
        col = geo_col or self.geo_field.name
        w, s, e, n = bbox.extent
        trans = self._trans_scale(col, -w, -s,
                                  scale / (e - w),
                                  scale / (n - s))
        g = AsText(trans)
        return self.annotate(pbf=g)

    def tile(self, bbox, z=0, format=None, clip=True):
        """Returns a GeoQuerySet intersecting a tile boundary.

        Arguments:
        bbox -- tile extent as geometry
        Keyword args:
        z -- tile zoom level used as basis for geometry simplification
        format -- vector tile format as str (pbf, geojson)
        clip -- clip geometries to tile boundary as boolean
        """
        # Tile grid uses 3857, but GeoJSON coordinates should be in 4326.
        tile_srid = 3857
        bbox = getattr(bbox, 'geos', bbox)
        clone = filter_geometry(self, intersects=bbox)
        field = clone.geo_field
        srid = field.srid
        sql = field.name
        try:
            tilew = self.tilewidths[z]
        except IndexError:
            tilew = self.tilewidths[-1]
        if bbox.srid != srid:
            bbox = bbox.transform(srid, clone=True)
        # Estimate tile width in degrees instead of meters.
        if bbox.srs.geographic:
            p = geos.Point(tilew, tilew, srid=tile_srid)
            p.transform(srid)
            tilew = p.x
        if clip:
            bufbox = bbox.buffer(tilew)
            sql = geofn.Intersection(sql, bufbox.envelope)
        sql = SimplifyPreserveTopology(sql, tilew)
        if format == 'pbf':
            return clone.pbf(bbox, geo_col=sql)
        sql = geofn.Transform(sql, 4326)
        return clone.annotate(**{format: sql})


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
            means = np.array([a.mean() for a in np.array_split(marr, periods)])
        obj = self[0]
        setattr(obj, fieldname, means)
        return [obj]

    def get(self, *args, **kwargs):
        # Need special handling of model instances with modified attributes,
        # otherwise they will be lost.
        if self._result_cache is not None:
            for obj in self._result_cache:
                for attr, val in kwargs.items():
                    if str(getattr(obj, attr)) == str(val):
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
        stat -- any numpy summary stat method as str (min/max/mean/etc)
        """
        if not hasattr(geom, 'num_coords'):
            raise TypeError('Need OGR or GEOS geometry, %s found' % type(geom))
        clone = self._clone()
        for obj in clone:
            arr = obj.array(geom)
            if arr is not None:
                if stat:
                    arr = aggregate1d(arr, stat)
                try:
                    arr = arr.squeeze()
                except ValueError:
                    pass
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
                fp = tempfile.NamedTemporaryFile(suffix='.%s' % format or '')
                with obj.raster() as r, r.warp(srid, fp.name) as w:
                    obj.image.file = fp
        return clone

    def zipfiles(self, path=None, arcdirname='data'):
        """Returns a .zip archive of selected rasters."""
        if path:
            fp = open(path, 'w+b')
        else:
            prefix = '%s-' % arcdirname
            fp = tempfile.NamedTemporaryFile(prefix=prefix, suffix='.zip')
        with zipfile.ZipFile(fp, mode='w') as zf:
            for obj in self:
                img = obj.image
                arcname = os.path.join(arcdirname, os.path.basename(img.name))
                try:
                    zf.write(img, arcname=arcname)
                except TypeError:
                    img.seek(0)
                    zf.writestr(arcname, img.read())
                    img.close()
        fp.seek(0)
        zobj = self.model(image=fp)
        return [zobj]
