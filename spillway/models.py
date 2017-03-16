import os
import datetime

from django.contrib.gis.db import models
from django.utils.deconstruct import deconstructible
from django.utils.translation import ugettext_lazy as _
import greenwich
from greenwich.io import MemFileIO
import numpy as np

from spillway.query import RasterQuerySet


# Workaround for migrations and FileField upload_to, see:
# https://code.djangoproject.com/ticket/22999
@deconstructible
class UploadDir(object):
    def __init__(self, path):
        self.path = path

    def __call__(self, instance, filename):
        return os.path.join(self.path, filename)

upload_to = UploadDir('data')


class AbstractRasterStore(models.Model):
    """Abstract model for raster data storage."""
    image = models.FileField(_('raster file'), upload_to=upload_to)
    width = models.IntegerField(_('width in pixels'))
    height = models.IntegerField(_('height in pixels'))
    geom = models.PolygonField(_('raster bounding polygon'))
    event = models.DateField()
    srs = models.TextField(_('spatial reference system'))
    minval = models.FloatField(_('minimum value'))
    maxval = models.FloatField(_('maximum value'))
    nodata = models.FloatField(_('nodata value'), blank=True, null=True)
    # Spatial resolution
    xpixsize = models.FloatField(_('West to East pixel resolution'))
    ypixsize = models.FloatField(_('North to South pixel resolution'))
    objects = RasterQuerySet()

    class Meta:
        unique_together = ('image', 'event')
        ordering = ['image']
        get_latest_by = 'event'
        abstract = True

    def __unicode__(self):
        return unicode(self.image)

    def clean_fields(self, *args, **kwargs):
        # Override this instead of save() so that fields are populated on
        # save() *or* manager methods like RasterStore.objects.create().
        if not self.image.storage.exists(self.image):
            self.image.save(self.image.name, self.image, save=False)
        with greenwich.Raster(self.image.path) as r:
            band = r[-1]
            bmin, bmax = band.GetMinimum(), band.GetMaximum()
            if bmin is None or bmax is None:
                bmin, bmax = band.ComputeRasterMinMax()
            self.geom = buffer(r.envelope.polygon.ExportToWkb())
            if r.sref.srid:
                self.geom.srid = r.sref.srid
            self.xpixsize, self.ypixsize = r.affine.scale
            self.width, self.height = r.size
            self.minval = bmin
            self.maxval = bmax
            self.nodata = r.nodata
            self.srs = r.sref.wkt
        if self.event is None:
            self.event = datetime.date.today()
        super(AbstractRasterStore, self).clean_fields(*args, **kwargs)

    def linear(self, limits=None, k=5):
        """Returns an ndarray of linear breaks."""
        start, stop = limits or (self.minval, self.maxval)
        return np.linspace(start, stop, k)

    def quantiles(self, k=5):
        """Returns an ndarray of quantile breaks."""
        arr = self.array()
        q = list(np.linspace(0, 100, k))
        return np.percentile(arr.compressed(), q)

    def save(self, *args, **kwargs):
        self.full_clean()
        super(AbstractRasterStore, self).save(*args, **kwargs)

    def array(self, geom=None):
        with self.raster() as r:
            return r.masked_array(geom)
        return np.array(())

    def raster(self):
        return greenwich.Raster(self.image.path)

    def convert(self, format=None, geom=None):
        imgpath = self.image.path
        # Handle format as .tif, tif, or tif.zip
        ext = format or os.path.splitext(imgpath)[-1][1:]
        ext = os.path.splitext(ext)[0]
        driver = greenwich.driver_for_path('base.%s' % ext)
        # No conversion is needed if the original format without clipping
        # is requested.
        if not geom and imgpath.endswith(ext):
            return
        memio = MemFileIO()
        if geom:
            with greenwich.Raster(imgpath) as r:
                with r.clip(geom) as clipped:
                    clipped.save(memio, driver)
        else:
            driver.copy(imgpath, memio.name)
        self.image.file = memio
