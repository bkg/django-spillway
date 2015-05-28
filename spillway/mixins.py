from rest_framework.exceptions import ValidationError


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

    def clean_params(self):
        """Returns a validated form dict from Request parameters."""
        form = self.query_form_class(
            self.request.query_params or self.request.data,
            self.request.FILES or None)
        if form.is_valid():
            return form.cleaned_data
        raise ValidationError(form.errors)
