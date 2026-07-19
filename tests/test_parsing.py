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


if __name__ == "__main__":
    unittest.main()
