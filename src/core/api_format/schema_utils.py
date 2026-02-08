"""JSON Schema cleaning utilities shared across Gemini-compatible providers.

Google Gemini's function declaration API does not support certain JSON Schema
fields.  These must be stripped recursively from tool parameter schemas before
forwarding to any Gemini-based upstream (native Gemini, Antigravity, etc.).
"""

from __future__ import annotations

from typing import Any

# JSON Schema fields unsupported by Google Gemini's function declaration API.
GEMINI_FORBIDDEN_SCHEMA_FIELDS: frozenset[str] = frozenset(
    {
        "$schema",
        "additionalProperties",
        "const",
        "contentEncoding",
        "contentMediaType",
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "multipleOf",
        "patternProperties",
        "propertyNames",
    }
)


def clean_gemini_schema(schema: dict[str, Any]) -> None:
    """Recursively strip JSON Schema fields unsupported by Gemini.

    Modifies *schema* in-place.  Recurses into ``properties``, ``items``,
    and ``anyOf`` / ``oneOf`` / ``allOf`` sub-schemas.
    """
    for field in GEMINI_FORBIDDEN_SCHEMA_FIELDS:
        schema.pop(field, None)

    props = schema.get("properties")
    if isinstance(props, dict):
        for prop_schema in props.values():
            if isinstance(prop_schema, dict):
                clean_gemini_schema(prop_schema)

    items = schema.get("items")
    if isinstance(items, dict):
        clean_gemini_schema(items)

    for combo_key in ("anyOf", "oneOf", "allOf"):
        combo = schema.get(combo_key)
        if isinstance(combo, list):
            for sub in combo:
                if isinstance(sub, dict):
                    clean_gemini_schema(sub)


__all__ = [
    "GEMINI_FORBIDDEN_SCHEMA_FIELDS",
    "clean_gemini_schema",
]
