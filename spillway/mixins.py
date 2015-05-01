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


class QueryFormMixin(object):
    """Provides form based handling of GET or POST requests."""
    query_form_class = None

    def get_query_form(self):
        """Returns a bound form instance."""
        return self.query_form_class(
            self.request.query_params or self.request.data,
            self.request.FILES or None)

    def clean_params(self):
        """Returns a validated form dict or an empty dict."""
        form = self.get_query_form()
        return form.cleaned_data if form.is_valid() else {}
