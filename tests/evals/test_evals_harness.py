"""Unit tests for the eval harness (fake mode + policy checks). Fast, offline."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.agent.models import AgentResponse
from tests.evals.run_evals import (
    INTENTS,
    check_policies,
    fake_agent,
    load_golden,
    main,
    run_evals,
)

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden_questions.json")


class TestGoldenSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = load_golden(GOLDEN_PATH)

    def test_schema_and_ids(self):
        self.assertTrue(len(self.golden) >= 12)
        ids = [e["id"] for e in self.golden]
        self.assertEqual(len(ids), len(set(ids)), "ids must be unique")
        for entry in self.golden:
            self.assertIn("id", entry)
            self.assertIn("question", entry)
            self.assertIn("notes", entry)
            self.assertIn(entry["expected_intent"], INTENTS)

    def test_strict_status_fields(self):
        for entry in self.golden:
            if entry["expected_intent"] == "WHAT_TO_DO":
                self.assertEqual(entry.get("expected_status"), "PENDING_APPROVAL")
            if entry.get("strict") is False:  # ambiguous entries must not be strict
                self.assertNotIn("expected_status", entry)


class TestFakeMode(unittest.TestCase):
    def test_fake_mode_end_to_end_all_pass(self):
        results = run_evals(load_golden(GOLDEN_PATH), live=False)
        self.assertEqual(len(results), len(load_golden(GOLDEN_PATH)))
        for entry, response, failures in results:
            self.assertIsInstance(response, AgentResponse)
            self.assertEqual(failures, [], f"{entry['id']} should pass in fake mode")

    def test_fake_mode_main_exit_zero(self):
        self.assertEqual(main(["--fake", "--golden", GOLDEN_PATH]), 0)

    def test_all_intents_covered(self):
        intents = {e["expected_intent"] for e in load_golden(GOLDEN_PATH)}
        self.assertEqual(intents, {"WHAT", "WHY", "WHAT_TO_DO", "OUT_OF_DOMAIN"})

    def test_fake_agent_matches_golden(self):
        for entry in load_golden(GOLDEN_PATH):
            self.assertEqual(
                check_policies(entry, fake_agent(entry)), [], f"{entry['id']} stub must be policy-clean"
            )


class TestPolicyChecks(unittest.TestCase):
    def _entry(self, intent, status=None, strict=True):
        entry = {"id": "t", "question": "q", "expected_intent": intent}
        if status:
            entry["expected_status"] = status
        if not strict:
            entry["strict"] = False
        return entry

    def _ok(self, intent="WHAT", status="OK", citations=("c1",), confidence=0.9):
        return AgentResponse(
            answer="a", intent=intent, citations=list(citations), confidence=confidence, status=status
        )

    def test_why_requires_citations(self):
        entry = self._entry("WHY")
        failures = check_policies(entry, self._ok(intent="WHY", citations=[]))
        self.assertTrue(any("non-empty citations" in f for f in failures))

    def test_whattodo_requires_pending_approval(self):
        entry = self._entry("WHAT_TO_DO", status="PENDING_APPROVAL")
        failures = check_policies(entry, self._ok(intent="WHAT_TO_DO", status="OK"))
        self.assertTrue(any("PENDING_APPROVAL" in f for f in failures))

    def _dict(self, intent="WHAT", status="OK", citations=("c1",), confidence=0.9):
        return {
            "answer": "a",
            "intent": intent,
            "citations": list(citations),
            "confidence": confidence,
            "status": status,
        }

    def test_confidence_range(self):
        entry = self._entry("WHAT")
        self.assertTrue(any("outside [0, 1]" in f for f in check_policies(entry, self._dict(confidence=1.5))))
        self.assertTrue(any("outside [0, 1]" in f for f in check_policies(entry, self._dict(confidence=-0.1))))
        self.assertEqual(check_policies(entry, self._dict(confidence=0.0)), [])
        self.assertEqual(check_policies(entry, self._dict(confidence=1.0)), [])

    def test_intent_mismatch_fails_strict_but_passes_relaxed(self):
        strict = self._entry("WHAT")
        self.assertTrue(any("intent mismatch" in f for f in check_policies(strict, self._dict(intent="WHY"))))
        relaxed = self._entry("WHAT", strict=False)
        self.assertEqual(check_policies(relaxed, self._dict(intent="WHY")), [])

    def test_error_intent_fails_relaxed_questions(self):
        relaxed = self._entry("WHAT", strict=False)
        self.assertTrue(any("ERROR" in f for f in check_policies(relaxed, self._dict(intent="ERROR"))))

    def test_status_mismatch(self):
        entry = self._entry("WHAT_TO_DO", status="PENDING_APPROVAL")
        failures = check_policies(entry, self._dict(intent="WHAT_TO_DO", status="ABSTAINED"))
        self.assertTrue(any("status mismatch" in f for f in failures))

    def test_valid_response_passes(self):
        entry = self._entry("WHY")
        self.assertEqual(check_policies(entry, self._ok(intent="WHY")), [])
        entry = self._entry("WHAT_TO_DO", status="PENDING_APPROVAL")
        self.assertEqual(check_policies(entry, self._ok(intent="WHAT_TO_DO", status="PENDING_APPROVAL")), [])

    def test_missing_fields_and_bad_types(self):
        entry = self._entry("WHAT")
        self.assertTrue(any("missing" in f for f in check_policies(entry, {"intent": "WHAT"})))
        self.assertTrue(any("invalid intent" in f for f in check_policies(entry, {"intent": "NOPE"})))
        self.assertTrue(
            any("not an AgentResponse" in f for f in check_policies(entry, "not-a-response"))
        )


if __name__ == "__main__":
    unittest.main()
