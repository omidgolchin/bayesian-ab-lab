"""Tests for the simulations, including the two checks the spec names:
the one-look false-positive rate must be 5% within Monte Carlo error, and
the grid expected losses used by the peeking simulator must match exact
quadrature.
"""

import numpy as np
import pytest
from scipy import stats as _stats

from src.bayesab.simulate import (one_look_fpr, required_n_per_arm,
                                  simulate_peeking, simulate_thompson)
from src.bayesab.stats import _expected_loss


def test_one_look_fpr_is_nominal():
    fpr = one_look_fpr(n_tests=20000, seed=7)
    mc_se = np.sqrt(0.05 * 0.95 / 20000)
    assert abs(fpr - 0.05) < 4 * mc_se


def test_grid_expected_loss_matches_exact():
    # Rebuild the grid computation for a few posterior pairs and compare.
    base_rate = 0.10
    grid = np.linspace(max(0.0, base_rate - 0.12),
                       min(1.0, base_rate + 0.12), 801)
    for xa, xb, n in [(30, 25, 250), (210, 190, 2000), (980, 1010, 10000)]:
        a_a, b_a = 1 + xa, 1 + n - xa
        a_b, b_b = 1 + xb, 1 + n - xb
        cdf_a = _stats.beta.cdf(grid, a_a, b_a)
        cdf_b = _stats.beta.cdf(grid, a_b, b_b)
        grid_loss_b = float(np.trapz(cdf_b * (1 - cdf_a), grid))
        exact_loss_b = _expected_loss(a_a, b_a, a_b, b_b)
        assert grid_loss_b == pytest.approx(exact_loss_b, abs=2e-5)


def test_peeking_fpr_grows_with_looks():
    out = simulate_peeking(n_tests=800, max_peeks=10, seed=3)
    classic = out["classic_fpr"]
    assert classic[0] == pytest.approx(0.05, abs=0.03)
    assert classic[-1] > classic[0] + 0.05  # peeking inflates the rate
    assert out["bayes_fpr"][-1] > 0.05  # the Bayes rule is not immune either


def test_required_n_per_arm_known_value():
    # Standard textbook case: p=0.10, MDE +2 points, 80% power -> ~3838/arm.
    n = required_n_per_arm(0.10, 0.02)
    assert 3700 < n < 4000
    # A bigger effect needs fewer visitors.
    assert required_n_per_arm(0.10, 0.05) < n


def test_thompson_beats_fixed_on_conversions_not_clarity_free():
    out = simulate_thompson(n_sims=300, horizon=800, seed=5)
    assert out["thompson"]["mean_conversions"] > out["fixed"]["mean_conversions"]
    assert out["thompson"]["regret_vs_oracle"] < out["fixed"]["regret_vs_oracle"]
