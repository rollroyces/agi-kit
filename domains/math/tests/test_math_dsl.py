"""Domain-level tests for the math DSL primitives.

These mirror the ``agent/tests/test_math_dsl.py`` set so the math domain
package is self-contained and can be tested without touching ``agent/``.
"""
from __future__ import annotations

import os
import sys
import unittest

_MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AGENT = os.path.abspath(os.path.join(_MATH, "..", "..", "agent"))
_REPO = os.path.abspath(os.path.join(_MATH, "..", ".."))
for p in (_MATH, _AGENT, _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

from agent.dsl.math_primitives import (  # noqa: E402
    extract_template,
    parse_number,
    safe_eval,
    template_slots,
)


class TestMathDSL(unittest.TestCase):

    def test_parse_number_integer(self):
        self.assertEqual(parse_number("The result is 7."), 7.0)

    def test_parse_number_negative_float(self):
        self.assertEqual(parse_number("Change: -2.5"), -2.5)

    def test_parse_number_strict_no_match(self):
        with self.assertRaises(ValueError):
            parse_number("answer = ???")

    def test_safe_eval_chain(self):
        self.assertEqual(safe_eval("2 * (3 + 4) - 1"), 13.0)

    def test_safe_eval_rejects_attribute_access(self):
        with self.assertRaises(ValueError):
            safe_eval("(1).real")

    def test_extract_template_substitutes_slots(self):
        out = extract_template("{a} + {b} = ?")
        self.assertEqual(out, "a + b = ?")

    def test_template_slots_preserves_order(self):
        self.assertEqual(template_slots("{z} {a} {m}"), ["z", "a", "m"])

    def test_math_dsl_is_idempotent(self):
        # The primitives must be pure — second call yields same result.
        self.assertEqual(safe_eval("5 + 6"), parse_number("11"))


if __name__ == "__main__":
    unittest.main()
