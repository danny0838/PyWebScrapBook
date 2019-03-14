:: Publish this package to PyPI.
::
:: System requirements:
:: * OS: Windows
::
@echo off
chcp 65001
python -m pip install --user --upgrade setuptools wheel
python setup.py sdist bdist_wheel
python -m pip install --user --upgrade twine
python -m twine upload --skip-existing dist/*
