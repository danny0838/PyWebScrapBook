:: Publish this package to PyPI.
::
:: System requirements:
:: * OS: Windows
::
@echo off
python -m pip install --user --upgrade setuptools wheel twine

:: prevent removed files from being included in the distribution
set src="webscrapbook.egg-info\SOURCES.txt"
if exist %src% del %src%
python setup.py clean --all

python setup.py sdist bdist_wheel
python -m twine upload --skip-existing dist/*
