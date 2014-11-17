from django.core.files.storage import default_storage
from rest_framework.renderers import BaseRenderer

from spillway import styles
from spillway.compat import mapnik


class MapnikRenderer(BaseRenderer):
    """Renders Mapnik stylesheets to tiled PNG."""
    mapfile = default_storage.path('map.xml')
    media_type = 'image/png'
    format = 'png'
    charset = None
    render_style = 'binary'

    def __init__(self, *args, **kwargs):
        super(MapnikRenderer, self).__init__(*args, **kwargs)
        self.stylename = 'Spectral_r'
        m = mapnik.Map(256, 256)
        try:
            mapnik.load_map(m, str(self.mapfile))
        except RuntimeError:
            pass
        m.buffer_size = 128
        m.srs = '+init=epsg:3857'
        self.map = m

    def append_layer(self, object, stylename):
        try:
            style = self.map.find_style(stylename)
        except KeyError:
            style = styles.make_raster_style()
            self.map.append_style(stylename, style)
            colors = styles.colors.get(stylename)
            bins = object.bin(k=len(colors))
            styles.add_colorizer_stops(style, bins, colors)
        try:
            layer = object.layer()
        except AttributeError:
            pass
        else:
            layer.styles.append(stylename)
            # Must append layer to map *after* appending style to it.
            self.map.layers.append(layer)

    def render(self, object, accepted_media_type=None, renderer_context=None):
        img = mapnik.Image(self.map.width, self.map.height)
        bbox = renderer_context.get('bbox') if renderer_context else None
        stylename = str(renderer_context.get('style') or
                        getattr(object, 'style', self.stylename))
        self.append_layer(object, stylename)
        # Zero area bounding boxes are invalid.
        if bbox and bbox.area:
            bbox.transform(self.map.srs)
            self.map.zoom_to_box(mapnik.Box2d(*bbox.extent))
            mapnik.render(self.map, img)
        return img.tostring(self.format)


class MapnikJPEGRenderer(MapnikRenderer):
    """Renders Mapnik stylesheets to tiled JPEG."""
    media_type = 'image/jpeg'
    format = 'jpeg'
