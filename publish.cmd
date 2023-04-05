:: Publish this package to PyPI.
::
:: System requirements:
:: * OS: Windows
::
@echo off
python -m pip install --upgrade build twine

:: Purge previously built files by bdist (wheel) to prevent deleted files
:: being included in the package.
set src="build"
if exist %src% rmdir /s /q %src%

python -m build --sdist --wheel
python -m twine upload --skip-existing dist/*
