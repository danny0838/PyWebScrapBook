#!/usr/bin/env python3
import sys
from setuptools import setup, find_packages
from inspect import cleandoc
import webscrapbook

with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='webscrapbook',
    version=webscrapbook.__version__,
    description=cleandoc(webscrapbook.__doc__),
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=webscrapbook.__author__,
    author_email=webscrapbook.__author_email__,
    url=webscrapbook.__homepage__,
    license=webscrapbook.__license__,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Content Management System',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        ],
    python_requires='~=3.7',
    install_requires=[
        'flask >= 1.1',
        'werkzeug >= 1.0.0',
        'jinja2 >= 2.10.1',
        'lxml >= 4.0',
        'commonmark >= 0.8',
        ],
    extras_require={
        'adhoc_ssl': ['cryptography'],
        },
    packages=find_packages(exclude=['tests']),
    package_data={
        'webscrapbook': [
            'resources/*.*',
            'themes/default/static/*.*',
            'themes/default/templates/*.*',
            'themes/default/locales/*/*.py',
            ],
        },
    entry_points={
        'console_scripts': [
            'webscrapbook = webscrapbook.cli:main',
            'wsb = webscrapbook.cli:main',
            'wsbview = webscrapbook.cli:view',
            ],
        },
    )
