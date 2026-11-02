import dataclasses
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import math
from typing import Any
import uuid


def to_canonical_dict(obj: Any) -> Any:
    """
    Recursively converts dataclasses, dicts, lists, enums, dates, and supported engine types
    into a canonical JSON-serializable structure with deterministic types.

    Preserves integer paise exactly.
    Rejects unsupported types and non-finite floats/decimals.
    """
    if obj is None:
        return None

    # bool is a subclass of int, so check bool first
    if isinstance(obj, bool):
        return obj

    if isinstance(obj, int):
        return obj

    if isinstance(obj, str):
        return obj

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Non-finite float value not allowed in canonical representation: {obj}")
        return obj

    if isinstance(obj, Decimal):
        if not obj.is_finite():
            raise ValueError(f"Non-finite Decimal value not allowed in canonical representation: {obj}")
        return str(obj)

    # datetime is a subclass of date, check datetime first
    if isinstance(obj, datetime):
        if obj.tzinfo is not None:
            return obj.astimezone(timezone.utc).isoformat()
        return obj.isoformat()

    if isinstance(obj, date):
        return obj.isoformat()

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, uuid.UUID):
        return str(obj)

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_canonical_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}

    if isinstance(obj, dict):
        return {str(k): to_canonical_dict(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_canonical_dict(v) for v in obj]

    if isinstance(obj, (set, frozenset)):
        items = [to_canonical_dict(v) for v in obj]
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True) if isinstance(x, (dict, list)) else str(x))

    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return to_canonical_dict(obj.model_dump())

    raise TypeError(f"Unsupported type for canonical serialization: {type(obj).__name__}")


def to_canonical_json(obj: Any) -> str:
    """
    Serializes an object or engine result into canonical JSON string.
    
    Guarantees:
    - Sorted keys at all levels
    - Compact separators (no trailing or leading whitespace around ':' and ',')
    - Exact integer paise preservation
    - Rejection of NaN, Infinity, and unsupported types
    - Stable ISO-8601 date and datetime strings
    """
    data = to_canonical_dict(obj)
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def from_canonical_json(json_str: str) -> Any:
    """Deserializes a canonical JSON string into Python primitives."""
    return json.loads(json_str)


def hash_snapshot(snapshot: Any) -> str:
    """
    Computes a deterministic SHA-256 hash (64 hex characters) of a FinancialSnapshot,
    Pydantic model, or raw financial data dictionary.

    Equivalent data structures with different key insertion orders produce
    identical hashes.
    """
    canonical_json = to_canonical_json(snapshot)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def hash_object(obj: Any) -> str:
    """Computes a deterministic SHA-256 hash of any serializable object."""
    canonical_json = to_canonical_json(obj)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
