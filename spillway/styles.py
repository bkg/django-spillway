from django.core.files.storage import default_storage
from django.db import connection
from greenwich import srs

from spillway.compat import mapnik
from spillway import colors, query

def add_colorizer_stops(style, bins, mcolors):
    rule = style.rules[0]
    symbolizer = rule.symbols[0]
    for value, color in zip(bins, mcolors):
        symbolizer.colorizer.add_stop(value, mapnik.Color(color))
    return style

def postgis_datasource(**kwargs):
    kwargs.setdefault('dbname', connection.settings_dict['NAME'])
    kwargs.setdefault('user', connection.settings_dict['USER'])
    return mapnik.PostGIS(**kwargs)

def build_map(queryset, tileform):
    data = tileform.cleaned_data if tileform.is_valid() else {}
    stylename = data.get('style')
    m = Map()
    layer = m.layer(queryset, stylename)
    m.zoom_bbox(data.get('bbox'))
    if layer.datasource.type() == mapnik.DataType.Raster:
        rcolors = colors.colormap.get(layer.stylename)
        bins = queryset.linear(data.get('limits'), k=len(rcolors))
        style = dict(m.map.styles).get(layer.stylename)
        add_colorizer_stops(style, bins, rcolors)
    return m


class Map(object):
    mapfile = default_storage.path('map.xml')

    def __init__(self):
        m = mapnik.Map(256, 256)
        try:
            mapnik.load_map(m, str(self.mapfile))
        except RuntimeError:
            pass
        m.buffer_size = 128
        m.srs = '+init=epsg:3857'
        self.map = m

    def layer(self, queryset, stylename=None):
        cls = VectorLayer if hasattr(queryset, 'geojson') else RasterLayer
        layer = cls(queryset)
        stylename = stylename or layer.stylename
        try:
            style = self.map.find_style(stylename)
        except KeyError:
            style = layer.make_style()
            self.map.append_style(stylename, style)
        layer.styles.append(stylename)
        self.map.layers.append(layer._layer)
        return layer

    def render(self, format, bbox=None):
        img = mapnik.Image(self.map.width, self.map.height)
        mapnik.render(self.map, img)
        return img.tostring(format)

    def zoom_bbox(self, bbox):
        if bbox and bbox.area:
            bbox.transform(self.map.srs)
            self.map.zoom_to_box(mapnik.Box2d(*bbox.extent))


class RasterLayer(object):
    default_style = 'Spectral_r'

    def __init__(self, obj, band=1):
        layer = mapnik.Layer(
            str(obj), srs.SpatialReference(obj.srs).proj4)
        layer.datasource = mapnik.Gdal(file=obj.image.path, band=band)
        self._layer = layer
        self.stylename = self.default_style

    def __getattr__(self, attr):
        return getattr(self._layer, attr)

    def make_style(self):
        style = mapnik.Style()
        rule = mapnik.Rule()
        symbolizer = self.make_symbolizer()
        rule.symbols.append(symbolizer)
        style.rules.append(rule)
        return style

    def make_symbolizer(self):
        symbolizer = mapnik.RasterSymbolizer()
        symbolizer.colorizer = mapnik.RasterColorizer(
            mapnik.COLORIZER_LINEAR, mapnik.Color(0, 0, 0, 255))
        return symbolizer


class VectorLayer(RasterLayer):
    default_style = 'polygon'

    def __init__(self, queryset):
        table = str(queryset.model._meta.db_table)
        sref = srs.SpatialReference(query.get_srid(queryset))
        layer = mapnik.Layer(table, sref.proj4)
        layer.datasource = postgis_datasource(table=table)
        self._layer = layer
        self.stylename = self.default_style

    def make_symbolizer(self):
        return mapnik.PolygonSymbolizer()
