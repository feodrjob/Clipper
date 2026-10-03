"""Strict JSON and schema checks shared by all providers."""

import json
from jsonschema import Draft202012Validator, SchemaError, ValidationError
from leviathan_clipper.llm.contracts import ProviderError


def strict_json(text):
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    try:
        return json.loads(text, parse_constant=reject_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ProviderError("The provider returned invalid JSON.", "invalid_response") from exc


def validate_response(text, schema):
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ProviderError("The requested output schema is invalid.", "configuration") from exc
    value = strict_json(text)
    try:
        Draft202012Validator(schema).validate(value)
    except (ValidationError, RecursionError) as exc:
        path = "/".join(str(part) for part in getattr(exc, "absolute_path", ()))
        raise ProviderError(f"Provider JSON does not match the output schema at {path or 'root'}.", "invalid_response") from exc
    return value
