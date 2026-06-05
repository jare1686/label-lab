"""Shared field-validation and JSON-structure utilities for source adapters.

These utilities enforce fail-closed validation with contextual error messages.
Identifiers are coerced to strings so downstream code treats IDs uniformly.
Booleans are rejected from numeric coercion to prevent ``True``/``False`` from
being silently treated as ``1``/``0``.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_json_object(path: Path) -> dict[str, object]:
    """Parse a JSON file and require the root value to be an object."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def require_object(value: object, field_name: str) -> dict[str, object]:
    """Require *value* to be a dict, returning it with string-coerced keys."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return {str(key): inner_value for key, inner_value in value.items()}


def require_object_list(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    """Require *key* in *payload* to be a list of objects."""
    raw_value = payload.get(key)
    if not isinstance(raw_value, list):
        raise ValueError(f"expected list field {key!r}")
    rows: list[dict[str, object]] = []
    for value in raw_value:
        if not isinstance(value, dict):
            raise ValueError(f"expected object entries inside {key!r}")
        rows.append({str(inner_key): inner_value for inner_key, inner_value in value.items()})
    return rows


def coerce_object(value: object) -> dict[str, object]:
    """Coerce *value* to a dict with string keys, defaulting to empty dict."""
    if not isinstance(value, dict):
        return {}
    return {str(key): inner_value for key, inner_value in value.items()}


def require_identifier(value: object, field_name: str) -> str:
    """Coerce an int, whole float, or non-empty string to a string identifier.

    Booleans are rejected so that ``True``/``False`` are not silently treated
    as ``1``/``0``.
    """
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must not be boolean")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"{field_name} must be a non-empty string or integer identifier")


def require_non_empty_string(value: object, field_name: str) -> str:
    """Require *value* to be a non-empty string after stripping whitespace."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"{field_name} must be a non-empty string")


def require_positive_int(value: object, field_name: str) -> int:
    """Require *value* to coerce to a positive integer."""
    number = coerce_int(value, field_name)
    if number <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return number


def require_non_negative_int(value: object, field_name: str) -> int:
    """Require *value* to coerce to a non-negative integer."""
    number = coerce_int(value, field_name)
    if number < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return number


def require_numeric_list(
    value: object,
    field_name: str,
    *,
    expected_length: int | None = None,
) -> list[float]:
    """Require *value* to be a non-empty list of numbers.

    Optionally checks that the list has exactly *expected_length* elements.
    """
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list")
    numbers: list[float] = []
    for index, item in enumerate(value):
        if not is_number(item):
            raise ValueError(f"{field_name}[{index}] must be numeric")
        numbers.append(float(item))
    if expected_length is not None and len(numbers) != expected_length:
        raise ValueError(f"{field_name} must contain exactly {expected_length} values")
    return numbers


def normalize_optional_string(value: object) -> str | None:
    """Return a stripped string if *value* is non-empty, otherwise ``None``."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def is_number(value: object) -> bool:
    """Return ``True`` if *value* is numeric, excluding booleans."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def coerce_int(value: object, field_name: str) -> int:
    """Coerce *value* to ``int``, accepting ints, whole floats, and numeric strings."""
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must not be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        return int(value)
    raise ValueError(f"{field_name} must be integer-compatible")
