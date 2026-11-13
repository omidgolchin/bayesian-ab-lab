"""Simulations: what happens when you peek, and what Thompson sampling buys.

Peeking. We simulate A/B tests in which A and B are *identical* (same true
rate), check the accumulating data every `peek_every` visitors per arm, and
stop at the first "positive" read. Two stopping rules are compared:

* classic -- stop when the two-sided pooled z-test gives p < alpha;
* bayes   -- stop when the expected loss of shipping the current leader
  falls below `loss_threshold` (a fixed number of rate points).

The share of identical tests that stop with a "positive" result is the
false-positive rate. For the classic rule with exactly one look it must come
out at alpha; Armitage, McPherson & Rowe (1969) tabulated how it grows with
the number of looks for accumulating normal data (1 look 5.0%, 5 looks
14.2%, 10 looks 19.3%, 20 looks 24.6%), and the binomial simulation here
lands in the same neighbourhood. The Bayesian rule is *not* immune: its
false-positive rate also climbs with the number of looks, just from a
different starting point. The honest fix is a sample size fixed in advance
from a power calculation, then one look.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from .stats import _prob_b_beats_a

ALPHA = 0.05
LOSS_THRESHOLD = 0.0005  # 0.05 percentage points of expected loss


# --------------------------------------------------------------------------
# peeking
# --------------------------------------------------------------------------

def _classic_pvalues(x_a: np.ndarray, x_b: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Pooled two-proportion z-test p-values for cumulative counts.

    x_a, x_b: (tests, peeks) cumulative conversions; n: (peeks,) per-arm n.
    """
    p_a = x_a / n
    p_b = x_b / n
    pooled = (x_a + x_b) / (2 * n)
    se = np.sqrt(np.maximum(pooled * (1 - pooled) * (2 / n), 1e-300))
    z = (p_b - p_a) / se
    return 2 * stats.norm.sf(np.abs(z))


def simulate_peeking(
    n_tests: int = 5000,
    base_rate: float = 0.10,
    peek_every: int = 250,
    max_peeks: int = 40,
    seed: int = 20261112,
) -> dict:
    """False-positive rate vs number of looks, for both stopping rules."""
    rng = np.random.default_rng(seed)
    blocks_a = rng.binomial(peek_every, base_rate, size=(n_tests, max_peeks))
    blocks_b = rng.binomial(peek_every, base_rate, size=(n_tests, max_peeks))
    cum_a = np.cumsum(blocks_a, axis=1)
    cum_b = np.cumsum(blocks_b, axis=1)
    ns = peek_every * np.arange(1, max_peeks + 1)

    # classic rule (vectorised)
    pvals = _classic_pvalues(cum_a, cum_b, ns)
    classic_hit = pvals < ALPHA
    classic_fpr = np.maximum.accumulate(classic_hit, axis=1).mean(axis=0)

    # Bayesian expected-loss rule. The expected loss of shipping an arm is
    # E[(other - arm)+] = integral of F_arm(t) * (1 - F_other(t)) dt, which
    # we evaluate for every test at once on a shared grid. The grid values
    # are checked against exact quadrature in the tests.
    grid = np.linspace(max(0.0, base_rate - 0.12),
                       min(1.0, base_rate + 0.12), 801)
    stopped = np.zeros(n_tests, dtype=bool)
    bayes_fpr = np.zeros(max_peeks)
    for k in range(max_peeks):
        n = float(ns[k])
        cdf_a = stats.beta.cdf(grid[None, :], 1 + cum_a[:, k][:, None],
                               1 + n - cum_a[:, k][:, None])
        cdf_b = stats.beta.cdf(grid[None, :], 1 + cum_b[:, k][:, None],
                               1 + n - cum_b[:, k][:, None])
        loss_choose_b = np.trapz(cdf_b * (1 - cdf_a), grid, axis=1)
        loss_choose_a = np.trapz(cdf_a * (1 - cdf_b), grid, axis=1)
        leader_is_b = cum_b[:, k] >= cum_a[:, k]
        leader_loss = np.where(leader_is_b, loss_choose_b, loss_choose_a)
        stopped |= leader_loss < LOSS_THRESHOLD
        bayes_fpr[k] = stopped.mean()

    return {
        "settings": {
            "n_tests": n_tests, "base_rate": base_rate,
            "peek_every": peek_every, "max_peeks": max_peeks,
            "alpha": ALPHA, "loss_threshold": LOSS_THRESHOLD, "seed": seed,
        },
        "peeks": list(range(1, max_peeks + 1)),
        "classic_fpr": [float(v) for v in classic_fpr],
        "bayes_fpr": [float(v) for v in bayes_fpr],
        "mc_se_classic": float(np.sqrt(0.25 / n_tests)),
    }


def one_look_fpr(n_tests: int = 20000, base_rate: float = 0.10,
                 n_per_arm: int = 1000, seed: int = 7) -> float:
    """False-positive rate of a single classic look; must be ~alpha."""
    rng = np.random.default_rng(seed)
    x_a = rng.binomial(n_per_arm, base_rate, n_tests)
    x_b = rng.binomial(n_per_arm, base_rate, n_tests)
    p = _classic_pvalues(x_a[:, None], x_b[:, None],
                         np.array([n_per_arm], dtype=float))
    return float((p[:, 0] < ALPHA).mean())


# --------------------------------------------------------------------------
# the honest fix: fix the size in advance
# --------------------------------------------------------------------------

def required_n_per_arm(base_rate: float, mde: float,
                       alpha: float = 0.05, power: float = 0.80) -> int:
    """Per-arm sample size for a two-proportion test (normal approximation)."""
    p1, p2 = base_rate, base_rate + mde
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    var = p1 * (1 - p1) + p2 * (1 - p2)
    return int(np.ceil((z_a + z_b) ** 2 * var / mde ** 2))


# --------------------------------------------------------------------------
# adaptive allocation: Thompson sampling vs a fixed 50/50 split
# --------------------------------------------------------------------------

def simulate_thompson(
    n_sims: int = 2000,
    horizon: int = 4000,
    p_a: float = 0.10,
    p_b: float = 0.12,
    seed: int = 20261112,
) -> dict:
    """Compare fixed 50/50 allocation with Thompson sampling on one test.

    Returns conversions, regret against the always-best-arm oracle, and how
    often the final Bayesian read is confident and right / confident and
    wrong (confidence: P(better arm wins) >= 0.95).
    """
    rng = np.random.default_rng(seed)

    def run(thompson: bool) -> dict:
        x_a = np.zeros(n_sims, dtype=int)
        x_b = np.zeros(n_sims, dtype=int)
        n_a = np.zeros(n_sims, dtype=int)
        n_b = np.zeros(n_sims, dtype=int)
        conv = np.zeros(n_sims, dtype=int)
        for _ in range(horizon):
            if thompson:
                pa = rng.beta(1 + x_a, 1 + n_a - x_a)
                pb = rng.beta(1 + x_b, 1 + n_b - x_b)
                choose_b = pb > pa
            else:
                choose_b = rng.random(n_sims) < 0.5
            hit = rng.random(n_sims) < np.where(choose_b, p_b, p_a)
            conv += hit
            x_b += choose_b & hit
            n_b += choose_b
            x_a += (~choose_b) & hit
            n_a += ~choose_b
        prob_b = np.array([
            _prob_b_beats_a(1 + int(xa), 1 + int(na) - int(xa),
                            1 + int(xb), 1 + int(nb) - int(xb))
            for xa, na, xb, nb in zip(x_a, n_a, x_b, n_b)
        ])
        if p_b == p_a:
            # Identical arms: any confident directional read is wrong;
            # "right" here means staying uncommitted (the honest read).
            conf_wrong = (prob_b >= 0.95) | (prob_b <= 0.05)
            conf_right = ~conf_wrong
        else:
            b_is_better = p_b > p_a
            conf_right = np.where(b_is_better, prob_b >= 0.95,
                                  prob_b <= 0.05)
            conf_wrong = np.where(b_is_better, prob_b <= 0.05,
                                  prob_b >= 0.95)
        return {
            "mean_conversions": float(conv.mean()),
            "confident_and_right": float(conf_right.mean()),
            "confident_and_wrong": float(conf_wrong.mean()),
        }

    fixed = run(False)
    ts = run(True)
    oracle = horizon * max(p_a, p_b)
    return {
        "settings": {"n_sims": n_sims, "horizon": horizon,
                     "p_a": p_a, "p_b": p_b, "seed": seed},
        "fixed": {**fixed,
                  "regret_vs_oracle": float(oracle - fixed["mean_conversions"])},
        "thompson": {**ts,
                     "regret_vs_oracle": float(oracle - ts["mean_conversions"])},
        "oracle_conversions": float(oracle),
    }
