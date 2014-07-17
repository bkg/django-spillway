from django.contrib.gis import forms
from spillway.fields import BoundingBoxField, SpatialReferenceField


class SpatialQueryForm(forms.Form):
    """Validates bounding box, serves as a common base for raster/vector
    data.
    """
    bbox = BoundingBoxField(required=False)


class GeometryQueryForm(SpatialQueryForm):
    """Validates vector data options."""
    geom = forms.GeometryField(required=False)
    # Tolerance value for geometry simplification
    simplify = forms.FloatField(required=False)
    srs = SpatialReferenceField(required=False)
