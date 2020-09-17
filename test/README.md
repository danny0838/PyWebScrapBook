## Unit Test

Enter this project directory and install it (adding `-e` is recommended):

    pip install -e .

Perform the unit tests:

    python -m unittest -v

NOTE: Some tests take advantage of the feature that dicts keep insertion order, which is an implementation detail in CPython 3.6 and a language feature since Python 3.7. As a result, some tests may fail for non-CPython 3.6 implementation.
