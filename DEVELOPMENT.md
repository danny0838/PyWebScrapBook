# Development

## Environment setup

1. Clone or download the source code from this repository.

2. Enter the project root and run: `pip install -r requirements-dev.txt`

## Code linting

1. Enter the project root and run: `flake8 .`

   > Optionally: automatically sort imports: `isort .`

## Install this package

1. Enter the project root and run: `pip install .`

   > Optionally: install in editable mode: `pip install -e .`

   > Optionally: install with extra dependencies, e.g.: `pip install .[adhoc_ssl]`

## Test

1. Install this package (recommended with editable mode)

1. Enter the project root and run: `python -m unittest`

   > Optionally: run tests with verbose output: `python -m unittest -v`

## Test against multiple environments

1. Enter the project root and run: `tox`

   > Optionally: run tests against the environments parallelly (with simplified logs): `tox p`

   > Optionally: run tests against specified environment(s), e.g.: `tox -e py313,py38`

## Build binary executable

1. Enter the project root and run: `tox -e build`

   > Optionally: build as onefile: `tox -e build -- --onefile`
