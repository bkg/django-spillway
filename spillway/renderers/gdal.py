import os

from rest_framework.renderers import BaseRenderer

def add_extsep(base, ext):
    return os.path.extsep.join((base, ext))


class BaseGDALRenderer(BaseRenderer):
    """Abstract renderer which encodes to a GDAL supported raster format."""
    media_type = 'application/octet-stream'
    format = None
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        fp = data['image']
        try:
            fp.seek(0, 2)
        except AttributeError:
            size = os.path.getsize(fp)
            fp = open(fp)
        else:
            size = fp.tell()
            fp.seek(0)
        self.set_filename(fp, renderer_context)
        self.set_response_length(size, renderer_context)
        return fp

    def set_filename(self, fp, renderer_context):
        # Chop off random part of filename for named tempfiles.
        if getattr(fp, 'delete', False):
            name = fp.name.split('-')[0]
        else:
            name = fp.name
        if not name.endswith(self.format):
            name = add_extsep(os.path.splitext(name)[0], self.format)
        type_name = 'attachment; filename=%s' % os.path.basename(name)
        try:
            renderer_context['response']['Content-Disposition'] = type_name
        except (KeyError, TypeError):
            pass

    def set_response_length(self, length, renderer_context):
        try:
            renderer_context['response']['Content-Length'] = length
        except (KeyError, TypeError):
            pass


class CSVRenderer(BaseGDALRenderer):
    """Renders a raster to CSV."""
    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'
    render_style = 'text'


class GeoTIFFRenderer(BaseGDALRenderer):
    """Renders a raster to GeoTIFF (.tif) format."""
    media_type = 'image/tiff'
    format = 'tif'


class GeoTIFFZipRenderer(BaseGDALRenderer):
    """Bundles GeoTIFF rasters in a zip archive."""
    media_type = 'application/zip'
    format = 'tif.zip'
    arcdirname = 'data'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if len(data) > 1:
            raise ValueError('Expected one-length sequence')
        return super(GeoTIFFZipRenderer, self).render(
            data[0], accepted_media_type, renderer_context)


class HFARenderer(BaseGDALRenderer):
    """Renders a raster to Erdas Imagine (.img) format."""
    format = 'img'


class HFAZipRenderer(GeoTIFFZipRenderer):
    """Bundles Erdas Imagine rasters in a zip archive."""
    format = 'img.zip'


class JPEGRenderer(BaseGDALRenderer):
    """Renders a raster to JPEG (.jpg) format."""
    media_type = 'image/jpeg'
    format = 'jpg'


class JPEGZipRenderer(GeoTIFFZipRenderer):
    """Bundles JPEG files in a zip archive."""
    format = 'jpg.zip'


class PNGRenderer(BaseGDALRenderer):
    """Renders a raster to PNG (.png) format."""
    media_type = 'image/png'
    format = 'png'


class PNGZipRenderer(GeoTIFFZipRenderer):
    """Bundles PNG files in a zip archive."""
    format = 'png.zip'
