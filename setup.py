#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(name='django-spillway',
      version='0.1.0',
      description='Geodata extensions for Django REST Framework',
      long_description=open('README.rst').read(),
      author='Brian Galey',
      author_email='bkgaley@gmail.com',
      url='https://github.com/bkg/django-spillway',
      packages=['spillway'],
      install_requires=['django', 'djangorestframework'],
      license='BSD',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Natural Language :: English',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
      ],
      test_suite='runtests.runtests')
