"""Unit tests for parsing.py.

Loaded by file path (not by package import) so these run with plain
stdlib unittest, without requiring Home Assistant to be installed.
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thermorossi"
    / "parsing.py"
)
_spec = importlib.util.spec_from_file_location("thermorossi_parsing", _MODULE_PATH)
parsing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parsing)


class ParseRegistersTests(unittest.TestCase):
    def test_parses_valid_payload(self) -> None:
        payload = {"registers": [[0, 10], [1, 20]]}
        self.assertEqual(parsing.parse_registers(payload), {0: 10, 1: 20})

    def test_rejects_non_dict_payload(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers(["not", "a", "dict"])

    def test_rejects_missing_registers_key(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"other": []})

    def test_rejects_non_list_registers(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"registers": "not-a-list"})

    def test_rejects_malformed_entry(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"registers": [[0]]})  # missing value

    def test_rejects_dict_shaped_entry(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"registers": [{"id": 0, "value": 10}]})

    def test_rejects_non_numeric_value(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"registers": [[0, "not-a-number"]]})

    def test_rejects_boolean_value(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"registers": [[0, True]]})

    def test_rejects_non_numeric_register_id(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"registers": [["0", 10]]})

    def test_rejects_boolean_register_id(self) -> None:
        with self.assertRaises(ValueError):
            parsing.parse_registers({"registers": [[True, 10]]})


class ComputeAlarmCodeTests(unittest.TestCase):
    def test_combines_msb_and_lsb(self) -> None:
        self.assertEqual(parsing.compute_alarm_code(msb=0x0001, lsb=0x0002), 0x00010002)

    def test_zero_when_no_alarms(self) -> None:
        self.assertEqual(parsing.compute_alarm_code(0, 0), 0)


class HostTests(unittest.TestCase):
    def test_normalize_host(self) -> None:
        self.assertEqual(parsing.normalize_host("  Stove.LAN "), "stove.lan")
        self.assertEqual(parsing.normalize_host("[FD00::1]"), "fd00::1")

    def test_is_valid_host(self) -> None:
        for host in ("192.168.1.100", "fd00::1", "stove", "stove.lan"):
            self.assertTrue(parsing.is_valid_host(host), host)
        for host in ("", "not a host", "http://stove", "stove:80", "-stove"):
            self.assertFalse(parsing.is_valid_host(host), host)

    def test_build_base_url(self) -> None:
        self.assertEqual(parsing.build_base_url("192.168.1.100"), "http://192.168.1.100")
        self.assertEqual(parsing.build_base_url("stove.lan"), "http://stove.lan")
        self.assertEqual(parsing.build_base_url("fd00::1"), "http://[fd00::1]")
        self.assertEqual(parsing.build_base_url("fe80::1%eth0"), "http://[fe80::1%25eth0]")


class DecodeTests(unittest.TestCase):
    def test_active_alarm_bits(self) -> None:
        self.assertEqual(parsing.active_alarm_bits(0), [])
        self.assertEqual(parsing.active_alarm_bits(0b1010 | (1 << 16)), [1, 3, 16])

    def test_decode_rtc(self) -> None:
        self.assertEqual(parsing.decode_rtc((7 << 11) | (23 << 6) | 59), (7, 23, 59))


if __name__ == "__main__":
    unittest.main()
