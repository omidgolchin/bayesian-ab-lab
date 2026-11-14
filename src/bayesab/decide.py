"""Decision layer of the A/B Test Decision Tool (reference implementation).

The page's JavaScript (docs/decide.js) mirrors these functions; the tests
check that the two agree. Everything here is standard method, cited where
it is used:

* Sample ratio mismatch: chi-square goodness of fit of the visitor split
  against the intended split (Kohavi, Tang & Xu, *Trustworthy Online
  Controlled Experiments*, 2020, ch. 21). Flag at p < 0.001.
* Always-valid p-value: the mixture sequential probability ratio test
  (mSPRT) with a normal mixing distribution, for the difference in two
  proportions (Johari, Koomen, Pekelis & Walsh, "Always valid inference",
  *Operations Research* 70(3), 2022). Valid however often you look.
* Equivalence: two one-sided tests (TOST), i.e. the 90% confidence interval
  for the difference lies inside +/- the smallest difference worth acting
  on (Schuirmann 1987).
* Sample size: the standard two-proportion formula (Fleiss, Levin & Paik,
  *Statistical Methods for Rates and Proportions*, 3rd ed., 2003),
  Bonferroni-adjusted when more than one variant is compared with control.
"""

from __future__ import annotations

import math

from scipy.stats import norm


def srm_p_value(n_a: int, n_b: int, share_b: float = 0.5) -> float:
    """Chi-square (1 df) p-value for the observed split against the plan."""
    total = n_a + n_b
    e_b = total * share_b
    e_a = total - e_b
    stat = (n_a - e_a) ** 2 / e_a + (n_b - e_b) ** 2 / e_b
    return float(2 * norm.sf(math.sqrt(stat)))


def always_valid_p(n_a: int, x_a: int, n_b: int, x_b: int, tau: float) -> float:
    """mSPRT always-valid p-value for H0: p_B = p_A (normal approximation).

    tau is the standard deviation of the normal mixing distribution over the
    true difference; the tool sets it to the smallest difference worth
    acting on.
    """
    r_a, r_b = x_a / n_a, x_b / n_b
    v = r_a * (1 - r_a) / n_a + r_b * (1 - r_b) / n_b
    if v <= 0 or tau <= 0:
        return 1.0
    d = r_b - r_a
    t2 = tau * tau
    log_lambda = 0.5 * math.log(v / (v + t2)) + t2 * d * d / (2 * v * (v + t2))
    return float(min(1.0, math.exp(-log_lambda)))


def equivalent(n_a: int, x_a: int, n_b: int, x_b: int, margin: float) -> bool:
    """TOST at alpha = 0.05: the 90% CI for p_B - p_A is inside +/- margin."""
    r_a, r_b = x_a / n_a, x_b / n_b
    se = math.sqrt(r_a * (1 - r_a) / n_a + r_b * (1 - r_b) / n_b)
    z = norm.ppf(0.95)
    lo, hi = (r_b - r_a) - z * se, (r_b - r_a) + z * se
    return -margin < lo and hi < margin


def sample_size_per_arm(p1: float, mde_abs: float, alpha: float = 0.05,
                        power: float = 0.8, versions: int = 2) -> int:
    """Visitors per version to detect an absolute difference mde_abs."""
    comparisons = max(1, versions - 1)
    a = alpha / comparisons
    p2 = p1 + mde_abs
    if not (0 < p1 < 1 and 0 < p2 < 1) or mde_abs == 0:
        raise ValueError("rates must lie in (0, 1) and the difference must be non-zero")
    p_bar = (p1 + p2) / 2
    z_a = norm.ppf(1 - a / 2)
    z_b = norm.ppf(power)
    num = (z_a * math.sqrt(2 * p_bar * (1 - p_bar))
           + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return int(math.ceil(num / mde_abs ** 2))


def detectable_lift(p1: float, n_per_arm: int, alpha: float = 0.05,
                    power: float = 0.8, versions: int = 2) -> float:
    """Smallest absolute difference detectable with n_per_arm (bisection)."""
    lo, hi = 1e-6, min(1 - p1, 0.999) - 1e-6
    for _ in range(80):
        mid = (lo + hi) / 2
        if sample_size_per_arm(p1, mid, alpha, power, versions) > n_per_arm:
            lo = mid
        else:
            hi = mid
    return hi
