"""Pydantic error code → user-friendly copy.

FU-099 / R-003 — the single source of truth for translating Pydantic's
developer-facing strings ("Input should be a valid integer", "String should
have at least 1 character", "Extra inputs not allowed") into copy that an
end user can actually act on. Owned server-side per the 2026-06-29 design
discussion (decision F1) so any future API client gets the same copy
without re-implementing the map.

Inclusion list is intentionally narrow (R-007): the Pydantic v2 error
codes our schemas actually emit. Unknown codes hit FRIENDLY_FALLBACK —
the same UX as a generic "please check this field" — and get added to
the table if real users hit them. We deliberately do not interpolate
constraint context (e.g. ``min_length`` from ``ctx``) in the first pass:
"Can't be empty." reads better than "Must be at least 1 character." in
the common case, and we don't currently ship a schema with a non-trivial
``min_length``. Extend ``ctx`` handling here when a real schema needs it.
The server is the one translator; the client renders what it is sent.
"""
from __future__ import annotations


# Pydantic v2 error type strings (``err["type"]``) → friendly copy.
PYDANTIC_FRIENDLY: dict[str, str] = {
    # Field presence / shape
    "missing":               "This field is required.",
    "extra_forbidden":       "This field isn't supported here.",
    "model_type":            "Not a valid value.",

    # Numeric
    "int_parsing":           "Must be a whole number.",
    "int_type":              "Must be a whole number.",
    "int_from_float":        "Must be a whole number, not a decimal.",
    "float_parsing":         "Must be a number.",
    "float_type":            "Must be a number.",
    "decimal_parsing":       "Must be a number.",
    "decimal_type":          "Must be a number.",
    "greater_than":          "Too small.",
    "greater_than_equal":    "Too small.",
    "less_than":             "Too large.",
    "less_than_equal":       "Too large.",
    "multiple_of":           "Not a valid step.",
    "finite_number":         "Must be a finite number.",

    # String
    "string_type":           "Must be text.",
    "string_too_short":      "Can't be empty.",
    "string_too_long":       "Too long.",
    "string_pattern_mismatch": "Not in the expected format.",

    # Boolean / enum / literal
    "bool_parsing":          "Must be true or false.",
    "bool_type":             "Must be true or false.",
    "literal_error":         "Not one of the allowed values.",
    "enum":                  "Not one of the allowed values.",

    # Collection sizes
    "too_short":             "Add at least one entry.",
    "too_long":              "Too many entries.",
    "list_type":             "Expected a list.",
    "dict_type":             "Expected an object.",

    # Identifiers / dates
    "uuid_parsing":          "Not a valid id.",
    "uuid_type":             "Not a valid id.",
    "datetime_parsing":      "Not a valid date / time.",
    "datetime_type":         "Not a valid date / time.",
    "date_parsing":          "Not a valid date.",
    "date_type":             "Not a valid date.",
    "time_parsing":          "Not a valid time.",
    "time_type":             "Not a valid time.",

    # Custom validators on the model
    "value_error":           "This value isn't valid.",
    "assertion_error":       "This value isn't valid.",
}

# Anything not in the map above. Same UX as the generic per-field copy a
# user would expect from "please check this field" — but devs still see
# the raw Pydantic msg in ``raw`` and the code in ``code``, so unknown
# codes are easy to spot and add.
FRIENDLY_FALLBACK = "This value isn't valid."


def translate_pydantic_error(code: str) -> str:
    """Return the friendly copy for *code*, or the fallback if unknown."""
    return PYDANTIC_FRIENDLY.get(code, FRIENDLY_FALLBACK)
