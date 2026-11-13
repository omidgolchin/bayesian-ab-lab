"""Score the LLM check against the calculator's ground truth.

Direct mode: the model's JSON is parsed; we score the decision (exact
match), the stated probability (within 10 percentage points of the
calculator's P(B beats A)), and whether the model flags the item's known
problem in its own words.

Code mode: the model's Python is extracted and run in the sandbox; we
score the computed probability (within 2 points) and p-value (within
0.02), derive a decision from the computed probability with the
probability-only rule (ship B at >= 0.95, ship A at <= 0.05), and check
the full reply text for a flagged problem.

A reply that cannot be parsed, or code that does not run, is a format
failure and is reported as one -- never silently dropped.
"""

from __future__ import annotations

import json
import re

from .items import PROBLEM_KEYWORDS
from .sandbox import run_code

_JSON_BLOCK = re.compile(r"\{.*?\}", re.DOTALL)
_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _first_json(text: str, key: str | None = None) -> dict | None:
    for match in _JSON_BLOCK.finditer(text or ""):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and (key is None or key in obj):
            return obj
    return None


def flags_problem(text: str, problem: str | None) -> bool:
    if not problem:
        return False
    low = (text or "").lower()
    return any(kw in low for kw in PROBLEM_KEYWORDS[problem])


def score_direct(row: dict, item: dict) -> dict:
    out = {"format_ok": False, "decision_correct": None,
           "prob_error_pp": None, "flagged_problem": None}
    obj = _first_json(row.get("text", ""), key="decision")
    if obj is None:
        return out
    out["format_ok"] = True
    out["decision_correct"] = obj.get("decision") == item["ground_truth_decision"]
    prob = obj.get("prob_b_better_percent")
    if isinstance(prob, (int, float)):
        out["prob_error_pp"] = abs(float(prob) - 100 * item["prob_b_beats_a"])
    concerns = str(obj.get("concerns", ""))
    if item["has_problem"]:
        out["flagged_problem"] = flags_problem(concerns, item["has_problem"])
    return out


def extract_code(text: str) -> str | None:
    match = _CODE_BLOCK.search(text or "")
    if match:
        return match.group(1)
    # fall back: the whole reply, if it looks like Python
    if "import" in (text or "") and "print" in (text or ""):
        return text
    return None


def score_code(row: dict, item: dict) -> dict:
    out = {"format_ok": False, "decision_correct": None,
           "prob_error_pp": None, "pvalue_error": None,
           "flagged_problem": None, "code_ran": False}
    text = row.get("text", "")
    if item["has_problem"]:
        out["flagged_problem"] = flags_problem(text, item["has_problem"])
    code = extract_code(text)
    if code is None:
        return out
    result = run_code(code)
    out["code_ran"] = result["ok"]
    if not result["ok"]:
        return out
    obj = _first_json(result["stdout"], key="prob_b_better")
    if obj is None:
        return out
    out["format_ok"] = True
    prob = float(obj["prob_b_better"])
    out["prob_error_pp"] = abs(prob - item["prob_b_beats_a"]) * 100
    if isinstance(obj.get("p_value"), (int, float)):
        out["pvalue_error"] = abs(float(obj["p_value"]) - item["p_value"])
    derived = ("ship_b" if prob >= 0.95 else
               "ship_a" if prob <= 0.05 else "keep_testing")
    if item["has_problem"] == "peeking":
        # For a peeked item the correct call is "do not ship on this
        # read", which a computed probability cannot express; code mode
        # is scored on probability accuracy and flagging for these items.
        out["decision_correct"] = None
    else:
        out["decision_correct"] = derived == item["ground_truth_decision"]
    return out


def score_row(row: dict, item: dict) -> dict:
    base = {"run_id": row["run_id"], "model": row["model_requested"],
            "item_id": row["item_id"], "mode": row["mode"],
            "status": row["status"]}
    if row["status"] != "ok":
        return {**base, "format_ok": False, "decision_correct": None,
                "prob_error_pp": None, "flagged_problem": None}
    scored = score_direct(row, item) if row["mode"] == "direct" \
        else score_code(row, item)
    return {**base, **scored}
