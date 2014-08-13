class GenericSerializerMixin(object):
    """Allows use of a model serializer class without a predefined model."""

    def get_serializer_class(self):
        cls = self.serializer_class
        # Make sure we have a model set for the serializer which allows the use
        # of additional default serializers than
        # settings.DEFAULT_MODEL_SERIALIZER_CLASS alone.
        if self.model and getattr(cls.Meta, 'model', False) != self.model:
            cls.Meta.model = self.model
        return cls


class QueryFormMixin(object):
    """Mixin to provide form based handling of GET or POST requests."""
    query_form_class = None

    def get_query_form(self):
        """Returns a bound form instance."""
        return self.query_form_class(
            self.request.QUERY_PARAMS or self.request.DATA,
            self.request.FILES or None)

    def clean_params(self):
        """Returns a validated form dict or an empty dict."""
        form = self.get_query_form()
        return form.cleaned_data if form.is_valid() else {}
