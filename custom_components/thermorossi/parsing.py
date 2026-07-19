"""Pure parsing/decoding helpers for the Thermorossi WiNET API.

Deliberately free of Home Assistant imports so this module (and its logic)
can be unit-tested without the full HA test harness.
"""
from __future__ import annotations


def parse_registers(payload: object) -> dict[int, int]:
    """Parse the 'registers' list from a get-registers API payload.

    Raises ValueError if the payload shape is unexpected.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object, got {type(payload).__name__}")

    registers = payload.get("registers")
    if not isinstance(registers, list):
        raise ValueError("missing or invalid 'registers' list in payload")

    try:
        result = {entry[0]: entry[1] for entry in registers}
    except (IndexError, TypeError, KeyError) as err:
        raise ValueError(f"malformed register entry: {err}") from err

    for reg_id, value in result.items():
        if not isinstance(reg_id, int) or isinstance(reg_id, bool):
            raise ValueError(f"non-numeric register id: {reg_id!r}")
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"non-numeric value for register {reg_id}: {value!r}")

    return result


def compute_alarm_code(msb: int, lsb: int) -> int:
    """Combine the two 16-bit alarm registers into a single 32-bit code."""
    return (msb << 16) | lsb
