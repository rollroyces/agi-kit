"""Math-specific DSL primitive tests (located in ``agent/tests`` because the
primitives live in ``agent/dsl/math_primitives.py``)."""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO = os.path.abspath(os.path.join(_ROOT, ".."))
sys.path.insert(0, _REPO)

from agent.dsl.math_primitives import (  # noqa: E402
    extract_template,
    parse_number,
    safe_eval,
    template_slots,
)
from agent.dsl.registry import all_names, get  # noqa: E402


class TestParseNumber(unittest.TestCase):

    def test_integer_text(self):
        self.assertEqual(parse_number("42"), 42.0)

    def test_integer_in_sentence(self):
        self.assertEqual(parse_number("The answer is 42."), 42.0)

    def test_float(self):
        self.assertEqual(parse_number("Approximately -3.14"), -3.14)

    def test_first_match_wins(self):
        # Should return the first match (3), not the larger one (10).
        self.assertEqual(parse_number("3 then 10"), 3.0)

    def test_no_number_raises(self):
        with self.assertRaises(ValueError):
            parse_number("no number here")


class TestSafeEval(unittest.TestCase):

    def test_basic_addition(self):
        self.assertEqual(safe_eval("3 + 4"), 7.0)

    def test_precedence(self):
        self.assertEqual(safe_eval("3 + 4 * 2"), 11.0)

    def test_parentheses_and_power(self):
        self.assertEqual(safe_eval("(1 + 2) ** 3"), 27.0)

    def test_unary_neg(self):
        self.assertEqual(safe_eval("-7 + 10"), 3.0)

    def test_rejects_function_call(self):
        with self.assertRaises(ValueError):
            safe_eval("__import__('os').system('echo')")

    def test_rejects_name(self):
        with self.assertRaises(ValueError):
            safe_eval("a + 1")


class TestExtractTemplate(unittest.TestCase):

    def test_substitutes_slot_names(self):
        tmpl = "If you have {x} apples and {y} are added, how many?"
        self.assertEqual(extract_template(tmpl),
                         "If you have x apples and y are added, how many?")

    def test_no_slots_returns_input(self):
        self.assertEqual(extract_template("plain text"), "plain text")

    def test_template_slots_returns_names(self):
        slots = template_slots("a {foo} and b {bar} and {foo}")
        self.assertEqual(slots, ["foo", "bar", "foo"])

    def test_template_slots_none_when_empty(self):
        self.assertIsNone(template_slots("no slots here"))

    def test_non_string_input_raises(self):
        with self.assertRaises(ValueError):
            extract_template(123)  # type: ignore[arg-type]


class TestRegistryIntegration(unittest.TestCase):

    def test_math_primitives_registered(self):
        names = set(all_names())
        self.assertIn("parse_number", names)
        self.assertIn("safe_eval", names)
        self.assertIn("extract_template", names)

    def test_lookup_by_name(self):
        # Use ``assertIsNotNone`` because the registry may load the function
        # via a different import path than the test's direct import.
        self.assertIsNotNone(get("parse_number"))
        self.assertIsNotNone(get("safe_eval"))
        self.assertIsNotNone(get("extract_template"))
        # The names must resolve to *callables*.
        self.assertTrue(callable(get("parse_number")))
        self.assertTrue(callable(get("safe_eval")))
        self.assertTrue(callable(get("extract_template")))


if __name__ == "__main__":
    unittest.main()
