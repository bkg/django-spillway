from rest_framework import exceptions
from rest_framework.renderers import TemplateHTMLRenderer
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
                fields = '__all__'
        return DefaultSerializer


class ResponseExceptionMixin(object):
    """Handle response exceptions by negotating among default renderers.

    The default exception handler passes error message dicts to the renderer
    which should be avoided with GDAL and Mapnik renderers, e.g. we wouldn't
    want a 404 returned as image/png.
    """

    def handle_exception(self, exc):
        response = super(ResponseExceptionMixin, self).handle_exception(exc)
        renderers = tuple(api_settings.DEFAULT_RENDERER_CLASSES)
        accepted = getattr(self.request, 'accepted_renderer', None)
        if (response.exception and accepted
                and not isinstance(accepted, renderers)):
            conneg = self.get_content_negotiator()
            try:
                render_cls, mtype = conneg.select_renderer(
                    self.request, renderers, self.format_kwarg)
            except exceptions.NotAcceptable:
                render_cls = TemplateHTMLRenderer
                mtype = render_cls.media_type
            self.request.accepted_renderer = render_cls()
            self.request.accepted_media_type = mtype
        return response
