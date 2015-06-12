#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='django-spillway',
      version='0.4.3',
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
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Natural Language :: English',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
      ],
      test_suite='runtests.runtests')
