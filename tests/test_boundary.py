"""Unit tests for the ActionBoundary itself — the shape, not the policy."""

from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("KESTREL_DB", os.path.join(tempfile.gettempdir(), "kestrel-test.db"))

from kestrel import db  # noqa: E402
from kestrel.boundary import ActionBoundary, Session, ToolRequest  # noqa: E402
from kestrel.events import DENY, LOG  # noqa: E402
from kestrel.tools import narrow  # noqa: E402
from kestrel.tools.registry import REGISTRY  # noqa: E402


def setUpModule() -> None:
    db.init(reset=True)
    REGISTRY.replace_all(list(narrow.SPECS))


class BoundaryShape(unittest.TestCase):
    def setUp(self) -> None:
        REGISTRY.reset_invocations()
        self.boundary = ActionBoundary()
        self.session = Session("t", 1001, ("customer",))

    def test_every_decision_emits_an_event(self) -> None:
        before = len(LOG)
        self.boundary.execute(
            ToolRequest("get_order", {"order_id": 91826}), self.session
        )
        self.assertGreater(len(LOG) - before, 0,
                           "the boundary decided but emitted nothing")

    def test_checks_run_in_the_taught_order(self) -> None:
        names = [n for n, _ in ActionBoundary.CHECK_ORDER]
        self.assertEqual(
            names,
            ["validate_arguments", "authorize_identity", "scope_resources",
             "business_rules", "require_approval", "apply_limits"],
        )

    def test_a_control_that_raises_fails_closed(self) -> None:
        class Boom:
            def validate_arguments(self, *a, **k):
                raise RuntimeError("kaboom")

            def __getattr__(self, name):
                raise AttributeError(name)

        boundary = ActionBoundary(controls=Boom())
        result = boundary.execute(
            ToolRequest("get_order", {"order_id": 91826}), self.session
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.denial.decision, DENY)

    def test_unknown_tool_does_not_execute(self) -> None:
        result = self.boundary.execute(
            ToolRequest("definitely_not_a_tool", {}), self.session
        )
        self.assertFalse(result.allowed)
        self.assertEqual(len(REGISTRY.invocations), 0)


if __name__ == "__main__":
    unittest.main()
