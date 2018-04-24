#!/usr/bin/env python
import os
import sys
import shutil
import tempfile
import traceback

from django.conf import settings
import django

TMPDIR = tempfile.mkdtemp(prefix='spillway_')

DEFAULT_SETTINGS = {
    'INSTALLED_APPS': (
        'django.contrib.staticfiles',
        'django.contrib.gis',
        'rest_framework',
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
    'STATIC_URL': '/static/',
    'TEMPLATES': [{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
    }],
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
    except Exception:
        traceback.print_exc()
        status = 1
    finally:
        teardown()
    sys.exit(status)

if __name__ == '__main__':
    runtests()
