class FormMixin(object):
    """Mixin to provide form validation and data cleaning of GET or POST
    requests.
    """
    form_class = None

    @property
    def form(self):
        """Returns a validated form dict or an empty dict."""
        _form = getattr(self, '_form', False)
        if not _form:
            self._form = self.form_class(self.request.GET or self.request.POST,
                                         self.request.FILES or None)
            valid = self._form.is_valid()
        return self._form
