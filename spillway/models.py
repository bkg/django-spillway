import os
import datetime

from django.contrib.gis.db import models
from django.utils.deconstruct import deconstructible
from django.utils.translation import ugettext_lazy as _
import greenwich
import numpy as np

from spillway.compat import mapnik


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
    srs = models.CharField(_('spatial reference system'), max_length=256)
    minval = models.FloatField(_('minimum value'))
    maxval = models.FloatField(_('maximum value'))
    nodata = models.FloatField(_('nodata value'), blank=True, null=True)
    # Spatial resolution
    xpixsize = models.FloatField(_('West to East pixel resolution'))
    ypixsize = models.FloatField(_('North to South pixel resolution'))

    class Meta:
        unique_together = ('image', 'event')
        ordering = ['image']
        get_latest_by = 'event'
        abstract = True

    def __unicode__(self):
        return self.image.name

    def bin(self, k=5, quantiles=False):
        if not quantiles:
            return np.linspace(self.minval, self.maxval, k)
        with greenwich.Raster(self.image.path) as rast:
            arr = rast.masked_array()
        q = list(np.linspace(0, 100, k))
        return np.percentile(arr.compressed(), q)

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

    def save(self, *args, **kwargs):
        self.full_clean()
        super(AbstractRasterStore, self).save(*args, **kwargs)

    def layer(self, band=1):
        layer = mapnik.Layer(
            str(self), greenwich.SpatialReference(self.srs).proj4)
        layer.datasource = mapnik.Gdal(file=self.image.path, band=band)
        return layer
