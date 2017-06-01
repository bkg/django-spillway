import os
import collections
import tempfile
import zipfile

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
        self.set_filename(fp.name, renderer_context)
        self.set_response_length(size, renderer_context)
        return fp

    def set_filename(self, name, renderer_context):
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
        if isinstance(data, collections.Mapping):
            data = [data]
        zipname = add_extsep(self.arcdirname, self.format)
        ext = self.format.split(os.path.extsep)[0]
        self.set_filename(zipname, renderer_context)
        fp = tempfile.TemporaryFile(suffix='.%s' % self.format)
        with zipfile.ZipFile(fp, mode='w') as zf:
            for item in data:
                io = item['image']
                fname = os.path.basename(getattr(io, 'name', io))
                arcname = os.path.join(self.arcdirname, fname)
                if not arcname.endswith(ext):
                    arcname = add_extsep(arcname, ext)
                try:
                    zf.write(io, arcname=arcname)
                except TypeError:
                    io.seek(0)
                    zf.writestr(arcname, io.read())
                    io.close()
        self.set_response_length(fp.tell(), renderer_context)
        fp.seek(0)
        return fp


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
