"""Tests for the calculator.

The core check required by the spec: the exact posterior quantities must
agree with a brute-force Monte Carlo over the two posteriors, on three
cases. The Monte Carlo uses a fixed seed and a tolerance of about four
Monte Carlo standard errors.
"""

import numpy as np
import pytest

from src.bayesab.stats import analyze, bayesian_read, classic_read

CASES = [
    (100, 10, 100, 20),      # the documented check case
    (44700, 20037, 45489, 20120),  # Cookie-Cats-sized counts
    (60, 3, 55, 9),          # small samples
]


def _mc(n_a, x_a, n_b, x_b, draws=600_000, seed=20261112):
    rng = np.random.default_rng(seed)
    pa = rng.beta(1 + x_a, 1 + n_a - x_a, draws)
    pb = rng.beta(1 + x_b, 1 + n_b - x_b, draws)
    diff = pb - pa
    return {
        "prob": float(np.mean(pb > pa)),
        "loss_b": float(np.mean(np.maximum(pa - pb, 0))),
        "loss_a": float(np.mean(np.maximum(pb - pa, 0))),
        "lo": float(np.quantile(diff, 0.025)),
        "hi": float(np.quantile(diff, 0.975)),
        "se_prob": float(np.sqrt(0.25 / draws)),
    }


@pytest.mark.parametrize("case", CASES)
def test_bayesian_matches_monte_carlo(case):
    res = bayesian_read(*case)
    mc = _mc(*case)
    assert res.prob_b_beats_a == pytest.approx(mc["prob"], abs=4 * mc["se_prob"])
    assert res.expected_loss_choose_b == pytest.approx(mc["loss_b"], abs=0.002)
    assert res.expected_loss_choose_a == pytest.approx(mc["loss_a"], abs=0.002)
    assert res.diff_ci_low == pytest.approx(mc["lo"], abs=0.004)
    assert res.diff_ci_high == pytest.approx(mc["hi"], abs=0.004)


def test_check_case_known_values():
    res = analyze(100, 10, 100, 20)
    # Hand-checkable: rates 10% vs 20%, diff +10 points.
    assert res.classic.rate_a == pytest.approx(0.10)
    assert res.classic.rate_b == pytest.approx(0.20)
    assert res.classic.diff == pytest.approx(0.10)
    # Pooled z = 0.10 / sqrt(0.15*0.85*0.02) = 1.980 -> p ~= 0.0477
    assert res.classic.p_value == pytest.approx(0.0477, abs=0.001)
    assert 0.95 < res.bayesian.prob_b_beats_a < 0.99


def test_identical_groups_are_a_coin_flip():
    res = bayesian_read(1000, 100, 1000, 100)
    assert res.prob_b_beats_a == pytest.approx(0.5, abs=0.01)
    assert res.expected_loss_choose_a == pytest.approx(
        res.expected_loss_choose_b, abs=1e-6)


def test_classic_ci_covers_diff_and_shrinks_with_n():
    small = classic_read(100, 10, 100, 20)
    big = classic_read(10000, 1000, 10000, 2000)
    assert small.ci_low < small.diff < small.ci_high
    assert (big.ci_high - big.ci_low) < (small.ci_high - small.ci_low) / 5


def test_grid_pack_matches_exact():
    # The grid computation used for large samples must agree with the
    # exact formulas on a case where both are cheap to run.
    from src.bayesab.stats import (_diff_quantile, _expected_loss,
                                   _grid_pack, _prob_b_beats_a)

    a_a, b_a, a_b, b_b = 201, 1801, 225, 1777  # n = 2000 per arm
    pack = _grid_pack(a_a, b_a, a_b, b_b)
    assert pack["prob_b_beats_a"] == pytest.approx(
        _prob_b_beats_a(a_a, b_a, a_b, b_b), abs=0.002)
    assert pack["expected_loss_choose_b"] == pytest.approx(
        _expected_loss(a_a, b_a, a_b, b_b), abs=3e-5)
    lo = _diff_quantile(a_a, b_a, a_b, b_b, 0.025)
    hi = _diff_quantile(a_a, b_a, a_b, b_b, 0.975)
    assert pack["diff_ci"][0] == pytest.approx(lo, abs=0.0015)
    assert pack["diff_ci"][1] == pytest.approx(hi, abs=0.0015)


def test_decision_rule():
    from src.bayesab.stats import decision
    assert decision(0.99, 0.01, 0.0005) == "ship_b"
    assert decision(0.01, 0.0005, 0.01) == "ship_a"
    assert decision(0.80, 0.004, 0.001) == "keep_testing"
    # Very probable but expensive to be wrong -> keep testing.
    assert decision(0.99, 0.01, 0.005) == "keep_testing"


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        analyze(0, 0, 100, 10)
    with pytest.raises(ValueError):
        analyze(100, 101, 100, 10)
