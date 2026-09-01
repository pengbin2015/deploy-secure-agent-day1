"""The tests teams run to prove their fixes.

Two rules, both from the workshop brief:

  * assert on SecurityEvents, never on what the model said;
  * a control that never ran is not a control that passed.

Run with the stdlib, no pytest needed:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("KESTREL_DB", os.path.join(tempfile.gettempdir(), "kestrel-test.db"))

from kestrel import db  # noqa: E402
from kestrel.attacks.scenarios import SCENARIOS, for_day, get  # noqa: E402
from kestrel.boundary import ActionBoundary, Session  # noqa: E402
from kestrel.evidence import evidence_b, evidence_c  # noqa: E402
from kestrel.console.detectors import check_data_boundary  # noqa: E402
from kestrel.events import BREACH, LOG  # noqa: E402
from kestrel.attacks.payloads import PAYLOADS  # noqa: E402
from kestrel.tools.registry import REGISTRY  # noqa: E402
from kestrel.tools import narrow  # noqa: E402


def setUpModule() -> None:
    db.init(reset=True)
    REGISTRY.replace_all(list(narrow.SPECS))


class EvidenceB(unittest.TestCase):
    """Given the dangerous action, does the responsible control deny it?"""

    def _check(self, scenario_id: str) -> None:
        scenario = get(scenario_id)
        result = evidence_b(scenario, ActionBoundary())
        self.assertTrue(result.passed, f"{scenario_id}: {result.summary}")

    # -- Day 1 ---------------------------------------------------------
    def test_cross_tenant_order_leak(self) -> None:
        self._check("cross_tenant_order_leak")

    def test_direct_injection_refund(self) -> None:
        self._check("direct_injection_refund")

    def test_indirect_injection_helpdoc(self) -> None:
        self._check("indirect_injection_helpdoc")

    def test_blank_cheque_sql(self) -> None:
        self._check("blank_cheque_sql")

    def test_gift_note_injection(self) -> None:
        self._check("gift_note_injection")

    # -- Day 2 ---------------------------------------------------------
    def test_tool_result_injection(self) -> None:
        self._check("tool_result_injection")

    def test_helper_agent_inheritance(self) -> None:
        self._check("helper_agent_inheritance")

    def test_memory_poisoning_policy(self) -> None:
        self._check("memory_poisoning_policy")

    def test_external_api_payload(self) -> None:
        self._check("external_api_payload")

    def test_runaway_refund_loop(self) -> None:
        self._check("runaway_refund_loop")


class EvidenceC(unittest.TestCase):
    """No tool executes without a matching SecurityEvent.

    Every Evidence B case above can pass while a helper still calls a tool
    directly. This is the only test that sees that.
    """

    def test_mediation_invariant_over_a_real_turn(self) -> None:
        from kestrel.agent.graph import Kestrel

        REGISTRY.reset_invocations()
        boundary = ActionBoundary()
        agent = Kestrel(boundary=boundary)
        scenario = get("cross_tenant_order_leak")
        agent.handle(scenario.prompt, scenario.make_session(),
                     scenario_id=scenario.id)
        result = evidence_c(boundary)
        self.assertTrue(result.passed, result.summary)


class DetectorEvents(unittest.TestCase):
    def test_cross_tenant_data_is_observed_as_a_breach(self) -> None:
        LOG.clear()
        observed = check_data_boundary(
            "list_my_orders",
            [{"customer_id": 1002, "item": "Ultrabook"}],
            Session("test", 1001, ("customer",)),
        )
        event = LOG.all()[-1]

        self.assertTrue(observed)
        self.assertEqual(event.decision, BREACH)
        self.assertFalse(event.held)


class BeatTheValidator(unittest.TestCase):
    def test_payload_corpus_has_four_deterministic_and_one_semantic_case(self) -> None:
        self.assertEqual(len(PAYLOADS), 5)
        self.assertEqual(
            [payload.layer_expected for payload in PAYLOADS].count("semantic"), 1
        )
        self.assertEqual(
            sum(payload.layer_expected in ("structural", "content") for payload in PAYLOADS),
            4,
        )

    def test_no_gateway_does_not_fabricate_semantic_verdicts(self) -> None:
        from kestrel.__main__ import run_beat_validator

        old_llm = os.environ.get("KESTREL_LLM")
        os.environ["KESTREL_LLM"] = "scripted"
        try:
            LOG.clear()
            results = run_beat_validator()
        finally:
            if old_llm is None:
                os.environ.pop("KESTREL_LLM", None)
            else:
                os.environ["KESTREL_LLM"] = old_llm

        self.assertEqual(sum(result["decision"] == "DENY" for result in results), 4)
        self.assertEqual(
            [result["layer"] for result in results].count("semantic unavailable"), 1
        )


class ScenarioIntegrity(unittest.TestCase):
    """Guards on the corpus itself, so a broken scenario fails loudly."""

    def test_every_scenario_names_a_control_and_two_surfaces(self) -> None:
        for s in SCENARIOS:
            self.assertTrue(s.expected_control, s.id)
            self.assertIn(s.day, (1, 2), s.id)
            self.assertTrue(1 <= int(s.entry_surface) <= 8, s.id)
            self.assertTrue(1 <= int(s.expected_control_surface) <= 8, s.id)

    def test_both_days_are_covered(self) -> None:
        self.assertTrue(for_day(1))
        self.assertTrue(for_day(2))


if __name__ == "__main__":
    unittest.main()
