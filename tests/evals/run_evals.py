#!/usr/bin/env python
"""Lightweight eval harness for the SSI agent (stdlib only).

Modes:
  live   — calls run_agent(question) against the real LLM endpoint. Exit code 1
           if any question fails its policy checks.
  --fake — uses a scripted stub model so the harness plumbing and policy checks
           are verifiable offline (all fake expectations must pass).

Usage:
  .venv/bin/python tests/evals/run_evals.py --fake
  .venv/bin/python tests/evals/run_evals.py
"""
import argparse
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.agent.models import AgentResponse

INTENTS = ("WHAT", "WHY", "WHAT_TO_DO", "OUT_OF_DOMAIN", "ERROR")
STATUSES = ("OK", "PENDING_APPROVAL", "ABSTAINED", "ERROR")
DEFAULT_GOLDEN = os.path.join(os.path.dirname(__file__), "golden_questions.json")


def load_golden(path=DEFAULT_GOLDEN):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fake_agent(entry):
    """Scripted stub: returns an AgentResponse matching the golden expectation."""
    intent = entry["expected_intent"]
    return AgentResponse(
        answer=f"Fake answer for {entry['id']}",
        intent=intent,
        citations=[] if intent != "WHY" else ["fake://doc/" + entry["id"]],
        confidence=0.9,
        status={"WHAT_TO_DO": "PENDING_APPROVAL", "OUT_OF_DOMAIN": "ABSTAINED"}.get(intent, "OK"),
    )


def check_policies(entry, response):
    """Return a list of policy failures (empty list = pass).

    Accepts an AgentResponse or a plain dict so the checks can be unit-tested
    with deliberately invalid payloads (e.g. confidence outside [0, 1]).
    """
    failures = []
    if isinstance(response, AgentResponse):
        data = response.model_dump()
    elif isinstance(response, dict):
        data = response
    else:
        return [f"response is not an AgentResponse or dict: {type(response).__name__}"]

    missing = [k for k in ("answer", "intent", "citations", "confidence", "status") if k not in data]
    if missing:
        failures.append(f"missing required fields: {missing}")

    intent = data.get("intent")
    status = data.get("status")
    citations = data.get("citations") or []
    confidence = data.get("confidence")

    if intent not in INTENTS:
        failures.append(f"invalid intent {intent!r}")
    if status not in STATUSES:
        failures.append(f"invalid status {status!r}")
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        failures.append(f"confidence {confidence!r} outside [0, 1]")

    if entry.get("strict", True):
        if intent != entry["expected_intent"]:
            failures.append(
                f"intent mismatch: expected {entry['expected_intent']!r}, got {intent!r}"
            )
        if entry.get("expected_status") and status != entry["expected_status"]:
            failures.append(
                f"status mismatch: expected {entry['expected_status']!r}, got {status!r}"
            )
    elif intent == "ERROR":
        failures.append("ambiguous question classified as ERROR")

    if intent == "WHY" and not citations:
        failures.append("WHY intent requires non-empty citations")
    if intent == "WHAT_TO_DO" and status != "PENDING_APPROVAL":
        failures.append("WHAT_TO_DO intent requires status=PENDING_APPROVAL")
    return failures


def run_evals(golden, live=False):
    """Evaluate every golden entry; returns (results, failures) tuples.

    results: list of (entry, response_or_None, failures: list[str]).
    """
    results = []
    for entry in golden:
        try:
            if live:
                from src.agent.graph import run_agent  # lazy: heavy imports + live endpoint

                response = run_agent(entry["question"])
            else:
                response = fake_agent(entry)
            failures = check_policies(entry, response)
        except Exception as exc:  # noqa: BLE001 - harness must not die on one bad question
            response = None
            failures = [f"exception: {type(exc).__name__}: {exc}"]
        results.append((entry, response, failures))
    return results


def summarize(results):
    """Per-intent pass-rate table and overall totals."""
    by_intent = {}
    for entry, _, failures in results:
        bucket = by_intent.setdefault(entry["expected_intent"], {"pass": 0, "fail": 0})
        bucket["pass" if not failures else "fail"] += 1

    total_pass = sum(1 for _, _, f in results if not f)
    total = len(results)
    print("\n=== Summary by intent ===")
    for intent in sorted(by_intent):
        b = by_intent[intent]
        rate = b["pass"] / (b["pass"] + b["fail"])
        print(f"{intent:<14} {b['pass']}/{b['pass'] + b['fail']} passed ({rate:.0%})")
    print(f"\nOverall: {total_pass}/{total} passed")
    return total_pass, total


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the agent eval suite.")
    parser.add_argument("--fake", action="store_true", help="use the scripted stub model (offline)")
    parser.add_argument("--golden", default=DEFAULT_GOLDEN, help="path to the golden question set")
    args = parser.parse_args(argv)

    golden = load_golden(args.golden)
    print(f"Loaded {len(golden)} golden questions from {args.golden}")
    print(f"Mode: {'FAKE (stub model)' if args.fake else 'LIVE (run_agent)'}\n")

    results = run_evals(golden, live=not args.fake)

    for entry, response, failures in results:
        tag = "PASS" if not failures else "FAIL"
        intent = getattr(response, "intent", None) or (entry["expected_intent"] if failures else "?")
        detail = "; ".join(failures) if failures else ""
        print(f"{tag}  {entry['id']:<28} [{intent}] {detail}")

    total_pass, total = summarize(results)

    if args.fake:
        # Fake expectations must all pass; exit code stays 0 either way (verdict printed).
        if total_pass < total:
            print("WARNING: fake mode produced failures — stub or policy bug.")
        return 0
    return 0 if total_pass == total else 1


if __name__ == "__main__":
    sys.exit(main())
