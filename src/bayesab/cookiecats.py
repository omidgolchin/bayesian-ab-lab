"""The Cookie Cats analysis: gate_30 vs gate_40, read both ways.

For 1-day and 7-day retention: the classic read (difference, confidence
interval, p-value), the Bayesian read (probability that gate_40 beats
gate_30, expected losses, credible interval), and a bootstrap confidence
interval for the difference as a distribution-free check. Everything is
computed from the counts, so the analysis is exact given the data file.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .stats import analyze

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "cookie_cats.csv"


def load_counts(path: Path = DATA) -> dict:
    df = pd.read_csv(path)
    out = {}
    for version in ("gate_30", "gate_40"):
        sub = df[df["version"] == version]
        out[version] = {
            "n": int(len(sub)),
            "retention_1": int(sub["retention_1"].astype(bool).sum()),
            "retention_7": int(sub["retention_7"].astype(bool).sum()),
        }
    return out


def bootstrap_diff_ci(n_a: int, x_a: int, n_b: int, x_b: int,
                      reps: int = 20000, seed: int = 20261112) -> tuple[float, float]:
    """Percentile bootstrap CI for rate_b - rate_a, resampling users.

    The data are Bernoulli, so resampling users within each group is the
    same as drawing new binomial counts with the observed rates; that is
    what is done here.
    """
    rng = np.random.default_rng(seed)
    pa = rng.binomial(n_a, x_a / n_a, reps) / n_a
    pb = rng.binomial(n_b, x_b / n_b, reps) / n_b
    diff = pb - pa
    return float(np.quantile(diff, 0.025)), float(np.quantile(diff, 0.975))


def analyze_cookie_cats(path: Path = DATA) -> dict:
    counts = load_counts(path)
    result = {"counts": counts, "metrics": {}}
    for metric in ("retention_1", "retention_7"):
        a, b = counts["gate_30"], counts["gate_40"]
        res = analyze(a["n"], a[metric], b["n"], b[metric])
        lo, hi = bootstrap_diff_ci(a["n"], a[metric], b["n"], b[metric])
        result["metrics"][metric] = {
            "rate_a": res.classic.rate_a,
            "rate_b": res.classic.rate_b,
            "diff": res.classic.diff,
            "classic_ci": [res.classic.ci_low, res.classic.ci_high],
            "p_value": res.classic.p_value,
            "prob_b_beats_a": res.bayesian.prob_b_beats_a,
            "expected_loss_choose_a": res.bayesian.expected_loss_choose_a,
            "expected_loss_choose_b": res.bayesian.expected_loss_choose_b,
            "bayes_diff_ci": [res.bayesian.diff_ci_low,
                              res.bayesian.diff_ci_high],
            "bootstrap_ci": [lo, hi],
            "classic_sentence": res.classic.sentence,
            "bayesian_sentence": res.bayesian.sentence,
        }
    return result
