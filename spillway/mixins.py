class QueryFormMixin(object):
    """Mixin to provide form based handling of GET or POST requests."""
    query_form_class = None

    def get_query_form(self):
        """Returns a validated form dict or an empty dict."""
        return self.query_form_class(
            self.request.QUERY_PARAMS or self.request.DATA,
            self.request.FILES or None)
