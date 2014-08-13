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
