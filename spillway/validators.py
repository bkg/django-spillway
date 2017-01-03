from django import forms
from django.utils.deconstruct import deconstructible
from django.utils.translation import ugettext_lazy as _


@deconstructible
class GeometrySizeValidator(object):
    """Field validator to limit geometries to a given area."""
    message = _('Max area exceeded.')
    code = 'invalid'

    def __init__(self, max_area, srid=None):
        self.max_area = max_area
        self.srid = srid

    def __call__(self, geom):
        if not geom:
            return
        if self.srid and geom.srid != self.srid:
            geom.transform(self.srid)
        if (getattr(geom, 'ogr', geom).dimension > 1 and
                geom.area > self.max_area):
            raise forms.ValidationError(self.message, code=self.code)
