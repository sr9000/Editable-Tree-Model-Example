from typing import Any


class _coalesce:
    def __getitem__(self, item):
        if isinstance(item, tuple):
            for x in item:
                if x is not None:
                    return x
        else:
            return item


nn = _coalesce()  # Not None argument (the first one)

# def nn(*args) -> Any:
#     for x in args:
#         if x is not None:
#             return x
