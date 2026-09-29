"""Pure parsing/decoding helpers for the Thermorossi WiNET API.

Deliberately free of Home Assistant imports so this module (and its logic)
can be unit-tested without the full HA test harness.
"""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping

_HOSTNAME_RE = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
)


def normalize_host(host: str) -> str:
    """Strip whitespace, surrounding IPv6 brackets and lowercase the host."""
    host = host.strip().lower()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host


def is_valid_host(host: str) -> bool:
    """Return True if host is a valid IPv4/IPv6 address or hostname."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    return bool(_HOSTNAME_RE.match(host)) and len(host) <= 253


def build_base_url(host: str) -> str:
    """Return the base HTTP URL for host (IPv6 literals are bracketed)."""
    try:
        is_ipv6 = ipaddress.ip_address(host).version == 6
    except ValueError:
        is_ipv6 = False
    if is_ipv6:
        # A zone id ("fe80::1%eth0") must be percent-encoded inside a URL.
        return f"http://[{host.replace('%', '%25')}]"
    return f"http://{host}"


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


def active_alarm_bits(code: int) -> list[int]:
    """Return the indices of the bits set in a 32-bit alarm code, lowest first."""
    return [bit for bit in range(32) if code & (1 << bit)]


def decode_rtc(raw: int) -> tuple[int, int, int]:
    """Decode the RTC register into (weekday 1-7, hour, minute)."""
    return (raw >> 11) & 0x7, (raw >> 6) & 0x1F, raw & 0x3F


def format_chrono_time(raw: int) -> str:
    """Format a schedule register, encoded (hour << 8) | minute, as HH:MM."""
    hour, minute = (raw >> 8) & 0xFF, raw & 0xFF
    hour_label = f"{hour:02d}" if hour < 24 else "??"
    minute_label = f"{minute:02d}" if minute < 60 else "??"
    return f"{hour_label}:{minute_label}"


def decode_chrono(
    registers: Mapping[int, int], first_reg: int, days: int, slots_per_day: int
) -> list[list[str]] | None:
    """Decode the weekly schedule into one list of "HH:MM-HH:MM" slots per day.

    Each day spans 2 * slots_per_day consecutive registers, alternating start
    and stop. A slot whose start equals its stop is unused. Returns None if any
    schedule register is missing.
    """
    week: list[list[str]] = []
    for day in range(days):
        slots: list[str] = []
        for slot in range(slots_per_day):
            reg = first_reg + 2 * (day * slots_per_day + slot)
            start, stop = registers.get(reg), registers.get(reg + 1)
            if start is None or stop is None:
                return None
            if start != stop:
                slots.append(f"{format_chrono_time(start)}-{format_chrono_time(stop)}")
        week.append(slots)
    return week
