:: Publish this package to PyPI.
::
@echo off
set "dir=%~dp0.."
set "build=%dir%\build"
set "dist=%dir%\dist"

python -m pip install --upgrade build twine

:: Purge previously built files by bdist (wheel) to prevent deleted files
:: being included in the package.
if exist "%build%" rmdir /s /q "%build%"

python -m build --sdist --wheel "%dir%"
python -m twine upload --skip-existing "%dist%/*"
