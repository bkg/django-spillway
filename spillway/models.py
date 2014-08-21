import datetime

from django.contrib.gis.db import models
from django.utils.translation import ugettext_lazy as _
from greenwich import Raster

from .query import GeoQuerySet


# Temporary solution until QuerySet.as_manager() is available in 1.7.
class GeoManager(models.GeoManager):
    def get_query_set(self):
        return GeoQuerySet(self.model, using=self._db)

    def __getattr__(self, name):
        return getattr(self.get_query_set(), name)


class AbstractRasterStore(models.Model):
    """Abstract model for raster data storage."""
    image = models.FileField(_('raster file'), upload_to='data')
    geom = models.GeometryField()
    event = models.DateField()
    srs = models.CharField(_('spatial reference system'), max_length=256)
    minval = models.FloatField(_('minimum value'))
    maxval = models.FloatField(_('maximum value'))
    nodata = models.FloatField(_('nodata value'), blank=True, null=True)

    class Meta:
        unique_together = ('image', 'event')
        ordering = ['image']
        get_latest_by = 'event'
        abstract = True

    def __unicode__(self):
        return self.image.name

    def clean_fields(self, *args, **kwargs):
        with Raster(self.image) as r:
            band = r[-1]
            bmin, bmax = band.GetMinimum(), band.GetMaximum()
            if bmin is None or bmax is None:
                bmin, bmax = band.ComputeRasterMinMax()
            self.geom = buffer(r.envelope.to_geom().ExportToWkb())
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
