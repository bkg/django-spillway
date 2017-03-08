from django.core.files.storage import default_storage
from django.db import connection
from django.contrib.gis import gdal
from greenwich import srs
from rest_framework.exceptions import NotFound

from spillway.compat import mapnik
from spillway import colors, query

def make_dbsource(**kwargs):
    """Returns a mapnik PostGIS or SQLite Datasource."""
    if 'spatialite' in connection.settings_dict.get('ENGINE'):
        kwargs.setdefault('file', connection.settings_dict['NAME'])
        return mapnik.SQLite(wkb_format='spatialite', **kwargs)
    names = (('dbname', 'NAME'), ('user', 'USER'),
             ('password', 'PASSWORD'), ('host', 'HOST'), ('port', 'PORT'))
    for mopt, dopt in names:
        val = connection.settings_dict.get(dopt)
        if val:
            kwargs.setdefault(mopt, val)
    return mapnik.PostGIS(**kwargs)

def build_map(querysets, tileform):
    data = tileform.cleaned_data if tileform.is_valid() else {}
    stylename = data.get('style')
    m = Map()
    bbox = data.get('bbox')
    if bbox:
        m.zoom_bbox(bbox)
    for queryset in querysets:
        layer = m.layer(queryset, stylename)
        proj = mapnik.Projection(layer.srs)
        trans = mapnik.ProjTransform(proj, m.proj)
        env = trans.forward(layer.envelope())
        if not env.intersects(m.map.envelope()):
            raise NotFound('Tile not found: outside layer extent')
        if isinstance(layer, RasterLayer):
            layer.add_colorizer_stops(data.get('limits'))
    return m


class Map(object):
    mapfile = default_storage.path('map.xml')

    def __init__(self, width=256, height=256):
        m = mapnik.Map(width, height)
        try:
            mapnik.load_map(m, str(self.mapfile))
        except RuntimeError:
            pass
        m.buffer_size = 128
        m.srs = '+init=epsg:3857'
        self.proj = mapnik.Projection(m.srs)
        self.map = m

    def layer(self, queryset, stylename=None):
        """Returns a map Layer.

        Arguments:
        queryset -- QuerySet for Layer
        Keyword args:
        stylename -- str name of style to apply
        """
        cls = VectorLayer if hasattr(queryset, 'geojson') else RasterLayer
        layer = cls(queryset, style=stylename)
        try:
            style = self.map.find_style(layer.stylename)
        except KeyError:
            self.map.append_style(layer.stylename, layer.style())
        layer.styles.append(layer.stylename)
        self.map.layers.append(layer._layer)
        return layer

    def render(self, format):
        img = mapnik.Image(self.map.width, self.map.height)
        mapnik.render(self.map, img)
        return img.tostring(format)

    def zoom_bbox(self, bbox):
        """Zoom map to geometry extent.

        Arguments:
        bbox -- OGRGeometry polygon to zoom map extent
        """
        try:
            bbox.transform(self.map.srs)
        except gdal.GDALException:
            pass
        else:
            self.map.zoom_to_box(mapnik.Box2d(*bbox.extent))


class Layer(object):
    """Base class for a Mapnik layer."""

    def __getattr__(self, attr):
        return getattr(self._layer, attr)

    def style(self):
        """Returns a default Style."""
        style = mapnik.Style()
        rule = mapnik.Rule()
        self._symbolizer = self.symbolizer()
        rule.symbols.append(self._symbolizer)
        style.rules.append(rule)
        return style

    def symbolizer(self):
        """Returns a default Symbolizer."""
        raise NotImplementedError


class RasterLayer(Layer):
    """A Mapnik layer for raster data types."""

    def __init__(self, obj, band=1, style=None):
        self._rstore = obj
        layer = mapnik.Layer(
            str(obj), srs.SpatialReference(obj.srs).proj4)
        layer.datasource = mapnik.Gdal(file=obj.image.path, band=band)
        self._layer = layer
        self.stylename = style or 'Spectral_r'
        self._symbolizer = None

    def add_colorizer_stops(self, limits):
        rcolors = colors.colormap.get(self.stylename)
        if rcolors:
            bins = self._rstore.linear(limits, k=len(rcolors))
            symbolizer = self._symbolizer
            for value, color in zip(bins, rcolors):
                symbolizer.colorizer.add_stop(value, mapnik.Color(color))

    def symbolizer(self):
        symbolizer = mapnik.RasterSymbolizer()
        symbolizer.colorizer = mapnik.RasterColorizer(
            mapnik.COLORIZER_LINEAR, mapnik.Color(0, 0, 0, 0))
        return symbolizer


class VectorLayer(Layer):
    """A Mapnik layer for vector data types."""

    def __init__(self, queryset, style=None):
        table = str(queryset.model._meta.db_table)
        field = query.geo_field(queryset)
        sref = srs.SpatialReference(query.get_srid(queryset))
        layer = mapnik.Layer(table, sref.proj4)
        ds = make_dbsource(table=table, geometry_field=field.name)
        # During tests, the spatialite layer statistics are not updated and
        # return an invalid layer extent. Set it from the queryset.
        if not ds.envelope().valid():
            ex = ','.join(map(str, queryset.extent()))
            ds = make_dbsource(table=table, geometry_field=field.name,
                               extent=ex)
        layer.datasource = ds
        self._layer = layer
        self.stylename = style or self._layer.name
        self._symbolizer = None

    def symbolizer(self):
        symbolizers = {
            mapnik.DataGeometryType.Point: mapnik.PointSymbolizer,
            mapnik.DataGeometryType.LineString: mapnik.LineSymbolizer,
            mapnik.DataGeometryType.Polygon: mapnik.PolygonSymbolizer
        }
        return symbolizers.get(self._layer.datasource.geometry_type(),
                               mapnik.PolygonSymbolizer)()
