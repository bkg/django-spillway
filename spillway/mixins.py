from rest_framework.settings import api_settings


class ModelSerializerMixin(object):
    """Provides generic model serializer classes to views."""
    model_serializer_class = None

    def get_serializer_class(self):
        if self.serializer_class:
            return self.serializer_class
        class DefaultSerializer(self.model_serializer_class):
            class Meta:
                model = self.queryset.model
        return DefaultSerializer


class ResponseExceptionMixin(object):
    """Handle response exceptions by negotating among default renderers.

    The default exception handler passes error message dicts to the renderer
    which should be avoided with GDAL and Mapnik renderers, e.g. we wouldn't
    want a 404 returned as image/png.
    """

    def handle_exception(self, exc):
        response = super(ResponseExceptionMixin, self).handle_exception(exc)
        if response.exception:
            renderers = api_settings.DEFAULT_RENDERER_CLASSES
            conneg = self.get_content_negotiator()
            render_cls, mtype = conneg.select_renderer(
                self.request, renderers, self.format_kwarg)
            self.request.accepted_renderer = render_cls()
            self.request.accepted_media_type = mtype
        return response
