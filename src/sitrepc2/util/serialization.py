# src/sitrepc2/util/serialization.py

from dataclasses import is_dataclass, fields
from enum import Enum
from typing import Any, Type, TypeVar, get_origin, get_args

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Generic Serializer
# ---------------------------------------------------------------------------

def serialize(obj: Any):
    """
    Recursively convert dataclasses, Enums, lists, and dicts into
    JSON-serializable structures.
    """
    # dataclass → dict
    if is_dataclass(obj):
        return {f.name: serialize(getattr(obj, f.name)) for f in fields(obj)}

    # Enum → value
    if isinstance(obj, Enum):
        return obj.value

    # list → list
    if isinstance(obj, list):
        return [serialize(i) for i in obj]

    # dict → dict
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}

    # primitive → unchanged
    return obj


# ---------------------------------------------------------------------------
# Generic Deserializer (AUTODETECTING)
# ---------------------------------------------------------------------------

def deserialize(data: dict, cls: Type[T]) -> T:
    """
    Reconstruct dataclass instances from a dict. This matches usage inside
    gazetteer/index.py where deserialize(row, LocaleEntry) is needed.

    Supports:
      - nested dataclasses
      - lists of dataclasses
      - Enums
      - native float/int values already provided by caller
    """
    if not is_dataclass(cls):
        raise TypeError(f"deserialize() requires a dataclass type, got: {cls}")

    kwargs = {}

    for f in fields(cls):
        name = f.name
        ftype = f.type
        value = data.get(name)

        # If missing, just pass it as None/default
        if value is None:
            kwargs[name] = None
            continue

        origin = get_origin(ftype)

        # Nested dataclass
        if is_dataclass(ftype):
            kwargs[name] = deserialize(value, ftype)

        # list[...] handling
        elif origin is list:
            subtype = get_args(ftype)[0]
            if is_dataclass(subtype):
                kwargs[name] = [deserialize(v, subtype) for v in value]
            else:
                kwargs[name] = value

        # Enum handling
        elif isinstance(ftype, type) and issubclass(ftype, Enum):
            kwargs[name] = ftype(value)

        else:
            # Primitive (float, int, str)
            kwargs[name] = value

    return cls(**kwargs)
