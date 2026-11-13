"""The 30 A/B summaries used in the LLM check, and their ground truth.

The items are fixed by hand (not sampled), so the set is freezable and every
number can be re-checked. They cover six situations a person reading A/B
results actually meets: clear B wins, clear A wins, large-sample ties,
small samples with dramatic-looking percentages, results that were peeked
into existence, and borderline reads.

Ground truth comes from this repo's own calculator (`stats.analyze`):
the decision is the rule in `stats.decision`, with one override -- for an
item whose team stopped the test because it turned significant, the correct
decision is always "keep_testing", whatever the final numbers say, because
the stopping rule invalidates the read. Items carry `has_problem` when a
good reader should also *say* what is wrong (peeking, or a sample too small
to support the percentages), and the scorer looks for that in the model's
own words.
"""

from __future__ import annotations

from .stats import analyze, decision

_FULL = ("The test ran for its full planned course and collected the "
         "sample size set by a power calculation before it started.")
_PEEK = ("The team watched the results dashboard every day and stopped "
         "the test on {day}, the first day the result showed as "
         "statistically significant.")

# id, category, (n_a, x_a, n_b, x_b), metric story, context, has_problem
_RAW = [
    ("item01", "clear_b_win", (20000, 2000, 20000, 2300),
     "checkout completion rate", _FULL, None),
    ("item02", "clear_b_win", (5000, 500, 5000, 620),
     "free-trial signup rate", _FULL, None),
    ("item03", "clear_b_win", (12000, 3600, 11800, 3894),
     "email click-through rate", _FULL, None),
    ("item04", "clear_b_win", (3000, 90, 3000, 150),
     "purchase rate on a product page", _FULL, None),
    ("item05", "clear_b_win", (50000, 2500, 50000, 2750),
     "app install conversion rate", _FULL, None),
    ("item06", "clear_b_win", (8000, 1600, 8200, 1886),
     "newsletter signup rate", _FULL, None),
    ("item07", "clear_b_win", (1500, 600, 1500, 690),
     "onboarding completion rate", _FULL, None),
    ("item08", "clear_b_win", (25000, 12500, 25000, 13125),
     "search click-through rate", _FULL, None),
    ("item09", "clear_a_win", (10000, 1200, 10000, 1000),
     "checkout completion rate", _FULL, None),
    ("item10", "clear_a_win", (6000, 1800, 6000, 1560),
     "free-trial signup rate", _FULL, None),
    ("item11", "clear_a_win", (2000, 100, 2000, 60),
     "purchase rate on a product page", _FULL, None),
    ("item12", "clear_a_win", (30000, 6000, 30000, 5550),
     "email click-through rate", _FULL, None),
    ("item13", "tie_large", (20000, 2000, 20000, 2004),
     "checkout completion rate", _FULL, None),
    ("item14", "tie_large", (15000, 4500, 15000, 4470),
     "onboarding completion rate", _FULL, None),
    ("item15", "tie_large", (8000, 400, 8000, 404),
     "purchase rate on a product page", _FULL, None),
    ("item16", "tie_large", (40000, 8000, 40000, 7960),
     "newsletter signup rate", _FULL, None),
    ("item17", "tie_large", (5000, 2500, 5000, 2500),
     "search click-through rate", _FULL, None),
    ("item18", "tie_large", (100000, 3000, 100000, 3060),
     "app install conversion rate", _FULL, None),
    ("item19", "small_sample", (60, 6, 58, 11),
     "purchase rate on a new landing page",
     "The test ran its planned three days; traffic to the new page was "
     "much lower than expected.", "small_sample"),
    ("item20", "small_sample", (120, 3, 110, 9),
     "free-trial signup rate",
     "The test was stopped after three days because of an unrelated site "
     "outage, long before its planned sample size.", "small_sample"),
    ("item21", "small_sample", (45, 18, 47, 24),
     "onboarding completion rate in a small beta cohort", _FULL,
     "small_sample"),
    ("item22", "small_sample", (200, 20, 190, 28),
     "email click-through rate for a small send", _FULL, "small_sample"),
    ("item23", "small_sample", (30, 0, 30, 3),
     "purchase rate in a hallway usability test",
     "Each version was shown to one small group of testers.", "small_sample"),
    ("item24", "peeked", (2400, 240, 2350, 278),
     "checkout completion rate", _PEEK.format(day="day 14"), "peeking"),
    ("item25", "peeked", (5000, 1000, 5050, 1111),
     "free-trial signup rate", _PEEK.format(day="day 11"), "peeking"),
    ("item26", "peeked", (900, 45, 920, 68),
     "purchase rate on a product page", _PEEK.format(day="day 9"),
     "peeking"),
    ("item27", "peeked", (15000, 450, 15000, 510),
     "app install conversion rate",
     "The team checked the dashboard daily for three weeks and stopped "
     "the test the first day the result showed as statistically "
     "significant.", "peeking"),
    ("item28", "borderline", (1000, 100, 1000, 115),
     "checkout completion rate", _FULL, None),
    ("item29", "borderline", (3000, 900, 3000, 945),
     "email click-through rate", _FULL, None),
    ("item30", "borderline", (20000, 1000, 20000, 1070),
     "purchase rate on a product page", _FULL, None),
]

PROBLEM_KEYWORDS = {
    "peeking": ["peek", "optional stopping", "multiple look", "repeated",
                "checked daily", "checking daily", "daily check",
                "inflated", "false positive", "stopped when",
                "stopped as soon", "not valid", "invalid", "rerun",
                "re-run", "sequential", "looked at the data",
                "watching the dashboard", "multiple comparisons",
                "run it again", "run longer", "cannot trust",
                "can't trust", "not trustworthy", "cherry"],
    "small_sample": ["small sample", "too few", "low sample", "sample size",
                     "not enough data", "not enough visitors", "wide",
                     "uncertain", "uncertainty", "more data",
                     "underpowered", "few visitors", "tiny", "only 60",
                     "only 30", "only 45", "only 58", "limited data",
                     "insufficient"],
}


def load_items() -> list[dict]:
    items = []
    for item_id, category, (n_a, x_a, n_b, x_b), metric, context, problem in _RAW:
        res = analyze(n_a, x_a, n_b, x_b)
        truth = decision(res.bayesian.prob_b_beats_a,
                         res.bayesian.expected_loss_choose_a,
                         res.bayesian.expected_loss_choose_b)
        if problem == "peeking":
            truth = "keep_testing"  # a peeked result cannot justify shipping
        items.append({
            "id": item_id,
            "category": category,
            "n_a": n_a, "x_a": x_a, "n_b": n_b, "x_b": x_b,
            "metric": metric,
            "context": context,
            "has_problem": problem,
            "rate_a": x_a / n_a,
            "rate_b": x_b / n_b,
            "prob_b_beats_a": res.bayesian.prob_b_beats_a,
            "p_value": res.classic.p_value,
            "expected_loss_choose_a": res.bayesian.expected_loss_choose_a,
            "expected_loss_choose_b": res.bayesian.expected_loss_choose_b,
            "ground_truth_decision": truth,
        })
    return items


PILOT_IDS = ["item01", "item13", "item20", "item24", "item28"]
