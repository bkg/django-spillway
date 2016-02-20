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
