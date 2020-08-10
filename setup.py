#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='django-spillway',
      version='0.8.1',
      description='Geodata extensions for Django REST Framework',
      long_description=open('README.rst').read(),
      author='Brian Galey',
      author_email='bkgaley@gmail.com',
      url='https://github.com/bkg/django-spillway',
      packages=find_packages(exclude=['tests*']),
      include_package_data=True,
      install_requires=['django', 'djangorestframework>=3.1.0', 'greenwich>=0.3'],
      extras_require={'mapnik': ['Mapnik>=2.0']},
      license='BSD',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Natural Language :: English',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
      ],
      test_suite='runtests.runtests')
