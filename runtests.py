#!/usr/bin/env python
import os
import sys
import shutil
import tempfile

from django.conf import settings
import django

TMPDIR = tempfile.mkdtemp(prefix='spillway_')

DEFAULT_SETTINGS = {
    'INSTALLED_APPS': (
        'django.contrib.gis',
        'spillway',
        'tests',
    ),
    'DATABASES': {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.spatialite',
            'NAME': 'spillway.db',
            'TEST': {'NAME': os.path.join(TMPDIR, 'test.db')}
        }
    },
    'MEDIA_ROOT': TMPDIR,
    'MIDDLEWARE_CLASSES': (
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
    ),
    'ROOT_URLCONF': 'tests.urls',
    'REST_FRAMEWORK': {
        # Fix for Django 1.9:
        # https://github.com/tomchristie/django-rest-framework/issues/3494
        'UNAUTHENTICATED_USER': None
    }
}

def teardown():
    try:
        shutil.rmtree(TMPDIR)
    except OSError:
        print('Failed to remove {}'.format(TMPDIR))

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
    try:
        status = runner_class(
            verbosity=1, interactive=True, failfast=False).run_tests(['tests'])
    except:
        status = 1
    finally:
        teardown()
    sys.exit(status)

if __name__ == '__main__':
    runtests()
