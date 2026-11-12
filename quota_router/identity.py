"""Validate the operator's explicit declaration without installing or promoting it."""
import re

ORIGIN = "gcunharodrigues/hermes-quota-router"


def selection(value):
    if value is None:
        return None, "unknown"
    fields = {"schema", "environment", "channel", "revision", "origin"}
    if not isinstance(value, dict) or set(value) != fields:
        return None, "invalid"
    valid = (
        type(value["schema"]) is int and value["schema"] == 1
        and value["environment"] in ("development", "test")
        and value["channel"] == "candidate"
        and isinstance(value["revision"], str)
        and re.fullmatch(r"[0-9a-fA-F]{40}", value["revision"]) is not None
        and value["origin"] == ORIGIN
    )
    return (dict(value), "declared_not_verified") if valid else (None, "invalid")
