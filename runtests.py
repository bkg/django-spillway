#!/usr/bin/env python
import os
import sys

from django.conf import settings
import django

DEFAULT_SETTINGS = {
    'INSTALLED_APPS': (
        'spillway',
        'tests',
    ),
    'DATABASES': {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.spatialite',
            'NAME': ':memory:'
        }
    },
}

def runtests():
    if not settings.configured:
        settings.configure(**DEFAULT_SETTINGS)
    # Compatibility with Django 1.7's stricter initialization
    if hasattr(django, 'setup'):
        django.setup()
    parent = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, parent)
    try:
        from django.test.runner import DiscoverRunner
        runner_class = DiscoverRunner
    except ImportError:
        from django.test.simple import DjangoTestSuiteRunner
        runner_class = DjangoTestSuiteRunner
    failures = runner_class(
        verbosity=1, interactive=True, failfast=False).run_tests(['tests'])
    sys.exit(failures)

if __name__ == '__main__':
    runtests()
