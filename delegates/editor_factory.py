import sys

from editors import factory as _factory

sys.modules[__name__] = _factory
