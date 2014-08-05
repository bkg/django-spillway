import os
import tempfile
from wsgiref.util import FileWrapper
import zipfile

from django.contrib.gis.shortcuts import compress_kml
from django.template import loader, Context
from rest_framework.pagination import PaginationSerializer
from rest_framework.renderers import BaseRenderer
from greenwich.geometry import Geometry
from greenwich.io import MemFileIO
from greenwich.raster import Raster, driver_for_path

from spillway.collections import FeatureCollection


class BaseGeoRenderer(BaseRenderer):
    """Base renderer for geographic features."""

    def _collection(self, data, renderer_context=None):
        pageinfo = {}
        results_field = self._results_field(renderer_context)
        results = data
        if data and isinstance(data, dict):
            if results_field in data:
                results = data.pop(results_field)
                pageinfo = data
            else:
                results = [data]
        return FeatureCollection(features=results, **pageinfo)

    def _results_field(self, context):
        """Returns the view's pagination serializer results field or the
        default value.
        """
        try:
            view = context.get('view')
            return view.pagination_serializer_class.results_field
        except AttributeError:
            return PaginationSerializer.results_field


class GeoJSONRenderer(BaseGeoRenderer):
    """Renderer which serializes to GeoJSON.

    This renderer purposefully avoids reserialization of GeoJSON from the
    spatial backend which greatly improves performance.
    """
    media_type = 'application/geojson'
    format = 'geojson'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Returns *data* encoded as GeoJSON."""
        return str(self._collection(data, renderer_context))


class TemplateRenderer(BaseGeoRenderer):
    """Template based feature renderer."""
    template_name = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        collection = self._collection(data, renderer_context)
        template = loader.get_template(self.template_name)
        return template.render(Context({'features': collection['features']}))


class KMLRenderer(TemplateRenderer):
    """Renderer which serializes to KML."""
    media_type = 'application/vnd.google-earth.kml+xml'
    format = 'kml'
    template_name = 'spillway/placemarks.kml'


class KMZRenderer(KMLRenderer):
    """Renderer which serializes to KMZ."""
    media_type = 'application/vnd.google-earth.kmz'
    format = 'kmz'

    def render(self, *args, **kwargs):
        kmldata = super(KMZRenderer, self).render(*args, **kwargs)
        return compress_kml(kmldata)


class SVGRenderer(TemplateRenderer):
    """Renderer which serializes to SVG."""
    media_type = 'image/svg+xml'
    format = 'svg'
    template_name = 'spillway/features.svg'


class BaseGDALRenderer(BaseRenderer):
    """Abstract renderer which encodes to a GDAL supported raster format."""
    media_type = 'application/octet-stream'
    format = None
    arcdirname = 'data'

    @property
    def file_ext(self):
        return os.extsep + os.path.splitext(self.format)[0]

    def basename(self, item):
        """Returns the output filename.

        Arguments:
        item -- dict containing 'path'
        """
        fname = os.path.basename(item['path'])
        return os.path.splitext(fname)[0] + self.file_ext

    def get_context(self, renderer_context):
        view = renderer_context.get('view')
        try:
            form = view.get_query_form()
        except AttributeError:
            return {}
        return form.cleaned_data if form.is_valid() else {}

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        ctx = self.get_context(renderer_context)
        geom = ctx.get('g')
        if isinstance(data, dict):
            self.set_filename(self.basename(data), renderer_context)
            # No conversion is needed if the original format without clipping
            # is requested.
            if not geom and data['path'].endswith(self.format):
                path = data['path']
                self.set_response_length(os.path.getsize(path), renderer_context)
                return FileWrapper(open(path))
            data = [data]
        else:
            self.set_filename(self.arcdirname, renderer_context)
        driver = driver_for_path(self.file_ext.replace(os.extsep, ''))
        imgdata = []
        for item in data:
            memio = MemFileIO()
            if geom:
                # Convert to wkb for ogr.Geometry
                geom = Geometry(wkb=bytes(geom.wkb), srs=geom.srs.wkt)
                with Raster(item['path']) as r:
                    with r.clip(geom) as clipped:
                        clipped.save(memio, driver)
            else:
                driver.copy(item['path'], memio.name)
            imgdata.append(memio.read())
            memio.close()
        return imgdata

    def set_filename(self, name, renderer_context):
        type_name = 'attachment; filename=%s.%s' % (name, self.format)
        try:
            renderer_context['response']['Content-Disposition'] = type_name
        except KeyError:
            pass

    def set_response_length(self, length, renderer_context):
        try:
            renderer_context['response']['Content-Length'] = length
        except (TypeError, KeyError):
            pass


class HFARenderer(BaseGDALRenderer):
    """Renders a raster to Erdas Imagine (.img) format."""
    format = 'img'


class GeoTIFFRenderer(BaseGDALRenderer):
    """Renders a raster to GeoTIFF (.tif) format."""
    media_type = 'image/tiff'
    format = 'tif'


class GeoTIFFZipRenderer(BaseGDALRenderer):
    """Bundles GeoTIFF rasters in a zip archive."""
    media_type = 'application/zip'
    format = 'tif.zip'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if not data:
            return data
        rendered = super(GeoTIFFZipRenderer, self).render(
            data, accepted_media_type, renderer_context)
        fp = tempfile.TemporaryFile(suffix=os.extsep + self.format)
        zf = zipfile.ZipFile(fp, mode='w')
        fname = None
        for raster, attrs in zip(rendered, data):
            fname = os.path.join(self.arcdirname, self.basename(attrs))
            # Write the raster buffer if it exists, or fall back to the GeoTIFF
            # path for the full raster.
            try:
                zf.writestr(fname, raster)
            except TypeError:
                zf.write(raster, arcname=fname)
        zf.close()
        self.set_response_length(fp.tell(), renderer_context)
        fp.seek(0)
        return FileWrapper(fp)


class HFAZipRenderer(GeoTIFFZipRenderer):
    """Bundles Erdas Imagine rasters in a zip archive."""
    format = 'img.zip'
