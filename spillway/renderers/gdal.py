import os
import tempfile
import zipfile

from greenwich.geometry import Geometry
from greenwich.io import MemFileIO
from greenwich.raster import Raster, driver_for_path
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
        return os.extsep + os.path.splitext(self.format)[0]

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, dict):
            data = [data]
        self.set_filename(self.basename(data[0]), renderer_context)
        img = self._render_items(data, renderer_context)[0]
        # File contents could contain null bytes but not file names.
        try:
            isfile = os.path.isfile(img)
        except TypeError:
            isfile = False
        if isfile:
            self.set_response_length(os.path.getsize(img), renderer_context)
            img = open(img)
        return img

    def _render_items(self, items, renderer_context):
        renderer_context = renderer_context or {}
        params = renderer_context.get('params')
        geom = params and params.get('g')
        driver = driver_for_path(self.file_ext.replace(os.extsep, ''))
        if geom:
            # Convert to wkb for ogr.Geometry
            geom = Geometry(wkb=bytes(geom.wkb), srs=geom.srs.wkt)
        imgdata = []
        for item in items:
            imgpath = item['path']
            # No conversion is needed if the original format without clipping
            # is requested.
            if not geom and imgpath.endswith(self.file_ext):
                imgdata.append(imgpath)
                continue
            memio = MemFileIO()
            if geom:
                with Raster(imgpath) as r:
                    with r.clip(geom) as clipped:
                        clipped.save(memio, driver)
            else:
                driver.copy(imgpath, memio.name)
            imgdata.append(memio.read())
            memio.close()
        return imgdata

    def set_filename(self, name, renderer_context):
        type_name = 'attachment; filename=%s.%s' % (name, self.format)
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
        rendered = self._render_items(data, renderer_context)
        self.set_filename(self.arcdirname, renderer_context)
        fp = tempfile.TemporaryFile(suffix=os.extsep + self.format)
        with zipfile.ZipFile(fp, mode='w') as zf:
            for raster, attrs in zip(rendered, data):
                arcname = os.path.join(self.arcdirname, self.basename(attrs))
                # Attempt to write from the filename first, or fall back to the
                # file contents.
                try:
                    zf.write(raster, arcname=arcname)
                except TypeError:
                    zf.writestr(arcname, raster)
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
