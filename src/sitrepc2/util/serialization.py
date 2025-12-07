# src/sitrepc2/nlp/serialization.py

from dataclasses import is_dataclass, fields
from enum import Enum


# ---------------------------------------------------------------------------
# Generic Serializer
# ---------------------------------------------------------------------------

def serialize(obj):
    """
    Recursively convert dataclasses, Enums, lists, and dicts into
    JSON-serializable structures. Domain classes require no custom code.
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
# Generic Deserializer (optional)
# ---------------------------------------------------------------------------

def deserialize(cls, data):
    """
    Reconstructs dataclass instances recursively from serialized dicts.
    Requires cls to be a dataclass.
    Enum fields are reconstructed via Enum(field_type).
    """
    if not is_dataclass(cls):
        raise TypeError(f"deserialize() requires a dataclass, got {cls}")

    kwargs = {}
    for f in fields(cls):
        value = data.get(f.name)
        ftype = f.type

        # reconstruct nested dataclasses
        origin = getattr(ftype, "__origin__", None)

        if is_dataclass(ftype):
            kwargs[f.name] = deserialize(ftype, value)

        # list[...] handling
        elif origin is list:
            subt = ftype.__args__[0]
            if is_dataclass(subt):
                kwargs[f.name] = [deserialize(subt, v) for v in value]
            else:
                kwargs[f.name] = value

        # Enum reconstruction
        elif isinstance(ftype, type) and issubclass(ftype, Enum):
            kwargs[f.name] = ftype(value)

        else:
            kwargs[f.name] = value

    return cls(**kwargs)
