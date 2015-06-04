import os
import tempfile
import zipfile

from rest_framework.renderers import BaseRenderer


class BaseGDALRenderer(BaseRenderer):
    """Abstract renderer which encodes to a GDAL supported raster format."""
    media_type = 'application/octet-stream'
    format = None
    charset = None
    render_style = 'binary'

    def basename(self, item):
        """Returns the output filename.

        Arguments:
        item -- dict containing 'path'
        """
        fname = os.path.basename(item['path'])
        return os.path.splitext(fname)[0] + self.file_ext

    @property
    def file_ext(self):
        return '.%s' % os.path.splitext(self.format)[0]

    def render(self, data, accepted_media_type=None, renderer_context=None):
        self.set_filename(self.basename(data), renderer_context)
        img = data['file']
        try:
            imgdata = img.read()
        except AttributeError:
            self.set_response_length(os.path.getsize(img), renderer_context)
            imgdata = open(img)
        else:
            img.close()
        return imgdata


    def set_filename(self, name, renderer_context):
        type_name = 'attachment; filename=%s' % name
        try:
            renderer_context['response']['Content-Disposition'] = type_name
        except (KeyError, TypeError):
            pass

    def set_response_length(self, length, renderer_context):
        try:
            renderer_context['response']['Content-Length'] = length
        except (KeyError, TypeError):
            pass


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
        if isinstance(data, dict):
            data = [data]
        zipname = '%s.%s' % (self.arcdirname, self.format)
        self.set_filename(zipname, renderer_context)
        fp = tempfile.TemporaryFile(suffix='.%s' % self.format)
        with zipfile.ZipFile(fp, mode='w') as zf:
            for item in data:
                arcname = os.path.join(self.arcdirname, self.basename(item))
                io = item['file']
                try:
                    zf.writestr(arcname, io.read())
                except AttributeError:
                    zf.write(io, arcname=arcname)
                else:
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
