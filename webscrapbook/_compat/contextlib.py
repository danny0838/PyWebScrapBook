#!/usr/bin/env python3
# since Python 3.6
try:
    from contextlib import AbstractContextManager
except ImportError:
    import abc
    import _collections_abc

    class AbstractContextManager(abc.ABC):

        """An abstract base class for context managers."""

        def __enter__(self):
            """Return `self` upon entering the runtime context."""
            return self

        @abc.abstractmethod
        def __exit__(self, exc_type, exc_value, traceback):
            """Raise any exception triggered within the runtime context."""
            return None

        @classmethod
        def __subclasshook__(cls, C):
            if cls is AbstractContextManager:
                return _collections_abc._check_methods(C, "__enter__", "__exit__")
            return NotImplemented


# since Python 3.7
try:
    from contextlib import nullcontext
except ImportError:
    class nullcontext(AbstractContextManager):
        """Context manager that does no additional processing.
        Used as a stand-in for a normal context manager, when a particular
        block of code is only sometimes used with a normal context manager:
        cm = optional_cm if condition else nullcontext()
        with cm:
            # Perform operation, using optional_cm if condition is True
        """

        def __init__(self, enter_result=None):
            self.enter_result = enter_result

        def __enter__(self):
            return self.enter_result

        def __exit__(self, *excinfo):
            pass
