"""Classic and Bayesian reads of a two-proportion A/B test.

Classic read: difference in proportions, a Wald 95% confidence interval, and
a two-sided p-value from the pooled two-proportion z-test.

Bayesian read: independent Beta priors on the two rates (Beta(1, 1) by
default). The posteriors are Beta distributions, and everything reported is
computed from them exactly (up to numerical integration error):

* P(B beats A)            -- integral of pdf_B(x) * CDF_A(x)
* expected loss of a pick -- E[max(other - pick, 0)] under the posteriors
* a 95% credible interval for the difference p_B - p_A, from its exact
  distribution function F(d) = integral of pdf_A(x) * CDF_B(x + d).

The plain-language sentences are written by rules from these numbers, never
by a language model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate, stats

Z_95 = 1.959963984540054  # standard normal 97.5% quantile


# --------------------------------------------------------------------------
# result containers
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassicResult:
    rate_a: float
    rate_b: float
    diff: float            # rate_b - rate_a
    ci_low: float
    ci_high: float
    p_value: float
    sentence: str


@dataclass(frozen=True)
class BayesianResult:
    post_a_alpha: float
    post_a_beta: float
    post_b_alpha: float
    post_b_beta: float
    mean_a: float
    mean_b: float
    prob_b_beats_a: float
    expected_loss_choose_a: float   # E[max(p_B - p_A, 0)]
    expected_loss_choose_b: float   # E[max(p_A - p_B, 0)]
    diff_ci_low: float
    diff_ci_high: float
    sentence: str


@dataclass(frozen=True)
class ABAnalysis:
    n_a: int
    x_a: int
    n_b: int
    x_b: int
    classic: ClassicResult
    bayesian: BayesianResult


# --------------------------------------------------------------------------
# classic read
# --------------------------------------------------------------------------

def classic_read(n_a: int, x_a: int, n_b: int, x_b: int) -> ClassicResult:
    _validate(n_a, x_a, n_b, x_b)
    p_a = x_a / n_a
    p_b = x_b / n_b
    diff = p_b - p_a
    se = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    ci_low, ci_high = diff - Z_95 * se, diff + Z_95 * se
    p_pool = (x_a + x_b) / (n_a + n_b)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se_pool == 0:
        p_value = 1.0
    else:
        z = diff / se_pool
        p_value = float(2 * stats.norm.sf(abs(z)))
    return ClassicResult(
        rate_a=p_a, rate_b=p_b, diff=diff,
        ci_low=float(ci_low), ci_high=float(ci_high), p_value=p_value,
        sentence=_classic_sentence(diff, ci_low, ci_high, p_value),
    )


def _classic_sentence(diff: float, lo: float, hi: float, p: float) -> str:
    d_pp, lo_pp, hi_pp = diff * 100, lo * 100, hi * 100
    if p < 0.05:
        return (
            f"B's rate is {d_pp:+.2f} points from A's (95% CI {lo_pp:+.2f} to "
            f"{hi_pp:+.2f}). The p-value is {p:.3f}: if the two versions were "
            f"really identical, a gap at least this large would appear in "
            f"about {p * 100:.1f}% of identical experiments."
        )
    return (
        f"B's rate is {d_pp:+.2f} points from A's (95% CI {lo_pp:+.2f} to "
        f"{hi_pp:+.2f}), and the interval includes zero. The p-value is "
        f"{p:.3f}: a gap at least this large would appear in about "
        f"{p * 100:.0f}% of experiments where the two versions are identical, "
        f"so this test does not separate the two versions."
    )


# --------------------------------------------------------------------------
# Bayesian read
# --------------------------------------------------------------------------

def _prob_b_beats_a(a_a: float, b_a: float, a_b: float, b_b: float) -> float:
    """P(p_B > p_A) for independent Beta posteriors.

    Uses the closed-form series when all four parameters are integers
    (always true for integer priors), otherwise numerical integration.
    """
    if all(float(v).is_integer() for v in (a_a, b_a, a_b, b_b)):
        a_a, b_a, a_b, b_b = (int(v) for v in (a_a, b_a, a_b, b_b))
        total = 0.0
        for i in range(a_b):
            term = np.exp(
                _log_beta(a_a + i, b_a + b_b)
                - np.log(b_b + i)
                - _log_beta(1 + i, b_b)
                - _log_beta(a_a, b_a)
            )
            total += term
        return float(min(max(total, 0.0), 1.0))
    val, _ = integrate.quad(
        lambda x: stats.beta.pdf(x, a_b, b_b) * stats.beta.cdf(x, a_a, b_a),
        0.0, 1.0, epsabs=1e-12, limit=200,
    )
    return float(min(max(val, 0.0), 1.0))


def _log_beta(a: float, b: float) -> float:
    from scipy.special import betaln
    return float(betaln(a, b))


def _expected_loss(a_win: float, b_win: float, a_lose: float, b_lose: float) -> float:
    """E[max(p_win - p_lose, 0)] for independent Beta posteriors.

    E[(X - Y)+] = integral_0^1 pdf_Y(y) * E[(X - y)+] dy, and for a Beta
    variable E[(X - y)+] = mean_X * (1 - F_{a+1,b}(y)) - y * (1 - F_{a,b}(y)).
    """
    mean_win = a_win / (a_win + b_win)

    def integrand(y: float) -> float:
        sf = stats.beta.sf(y, a_win, b_win)
        sf_shifted = stats.beta.sf(y, a_win + 1, b_win)
        return stats.beta.pdf(y, a_lose, b_lose) * (mean_win * sf_shifted - y * sf)

    val, _ = integrate.quad(integrand, 0.0, 1.0, epsabs=1e-12, limit=200)
    return float(max(val, 0.0))


def _diff_quantile(a_a: float, b_a: float, a_b: float, b_b: float, q: float) -> float:
    """Quantile of p_B - p_A via its exact CDF and bisection."""

    def cdf(d: float) -> float:
        val, _ = integrate.quad(
            lambda x: stats.beta.pdf(x, a_a, b_a)
            * stats.beta.cdf(x + d, a_b, b_b),
            0.0, 1.0, epsabs=1e-11, limit=200,
        )
        return float(val)

    lo, hi = -1.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if cdf(mid) < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Grid computation for large samples.
#
# The exact formulas above are the reference definitions, but with tens of
# thousands of visitors the quadrature integrands become needle-shaped and
# the bisection over them crawls. For large samples (and only there), the
# same quantities are computed on a grid fitted to the two posteriors
# (mean +/- 10 sd, 2001 points): the probability and expected losses come
# from the CDF identity E[(other - arm)+] = integral of
# F_arm(t) (1 - F_other(t)) dt, and the credible interval for the
# difference from F_diff(d) = E[F_A(p_B - d)] on the same grid. The tests
# check grid values against the exact ones on cases where both run.
# ---------------------------------------------------------------------------

_GRID_POINTS = 2001
_LARGE_TOTAL = 2000  # total visitors above which the grid pack is used


def _grid_pack(a_a: float, b_a: float, a_b: float, b_b: float) -> dict:
    m_a = a_a / (a_a + b_a)
    m_b = a_b / (a_b + b_b)
    s_a = np.sqrt(m_a * (1 - m_a) / (a_a + b_a + 1))
    s_b = np.sqrt(m_b * (1 - m_b) / (a_b + b_b + 1))
    s = max(s_a, s_b)
    lo = max(0.0, min(m_a, m_b) - 10 * s)
    hi = min(1.0, max(m_a, m_b) + 10 * s)
    xs = np.linspace(lo, hi, _GRID_POINTS)
    cdf_a = stats.beta.cdf(xs, a_a, b_a)
    cdf_b = stats.beta.cdf(xs, a_b, b_b)
    pdf_a = stats.beta.pdf(xs, a_a, b_a)
    pdf_b = stats.beta.pdf(xs, a_b, b_b)
    prob = float(np.trapz(pdf_b * cdf_a, xs))
    loss_b = float(np.trapz(cdf_b * (1 - cdf_a), xs))
    loss_a = float(np.trapz(cdf_a * (1 - cdf_b), xs))
    # F_diff(d) = P(p_B - p_A <= d) = E over p_A of F_B(p_A + d)
    ds = np.linspace(lo - hi, hi - lo, 1201)
    fb_at = np.interp(
        np.clip(xs[None, :] + ds[:, None], lo, hi), xs, cdf_b,
        left=0.0, right=1.0,
    )
    d_cdf = np.trapz(pdf_a[None, :] * fb_at, xs, axis=1)
    d_cdf = np.maximum.accumulate(d_cdf)
    if d_cdf[-1] > 0:
        d_cdf = d_cdf / d_cdf[-1]
    ci_lo = float(np.interp(0.025, d_cdf, ds))
    ci_hi = float(np.interp(0.975, d_cdf, ds))
    return {"prob_b_beats_a": prob, "expected_loss_choose_a": loss_a,
            "expected_loss_choose_b": loss_b, "diff_ci": (ci_lo, ci_hi)}


def bayesian_read(
    n_a: int, x_a: int, n_b: int, x_b: int,
    prior_alpha: float = 1.0, prior_beta: float = 1.0,
) -> BayesianResult:
    _validate(n_a, x_a, n_b, x_b)
    a_a, b_a = prior_alpha + x_a, prior_beta + (n_a - x_a)
    a_b, b_b = prior_alpha + x_b, prior_beta + (n_b - x_b)
    if n_a + n_b > _LARGE_TOTAL:
        pack = _grid_pack(a_a, b_a, a_b, b_b)
        prob = pack["prob_b_beats_a"]
        loss_a = pack["expected_loss_choose_a"]
        loss_b = pack["expected_loss_choose_b"]
        lo, hi = pack["diff_ci"]
    else:
        prob = _prob_b_beats_a(a_a, b_a, a_b, b_b)
        loss_b = _expected_loss(a_a, b_a, a_b, b_b)  # choosing B loses if A wins
        loss_a = _expected_loss(a_b, b_b, a_a, b_a)  # choosing A loses if B wins
        lo = _diff_quantile(a_a, b_a, a_b, b_b, 0.025)
        hi = _diff_quantile(a_a, b_a, a_b, b_b, 0.975)
    mean_a = a_a / (a_a + b_a)
    mean_b = a_b / (a_b + b_b)
    return BayesianResult(
        post_a_alpha=a_a, post_a_beta=b_a, post_b_alpha=a_b, post_b_beta=b_b,
        mean_a=mean_a, mean_b=mean_b,
        prob_b_beats_a=prob,
        expected_loss_choose_a=float(loss_a),
        expected_loss_choose_b=float(loss_b),
        diff_ci_low=float(lo), diff_ci_high=float(hi),
        sentence=_bayesian_sentence(prob, loss_a, loss_b, lo, hi),
    )


def _bayesian_sentence(prob: float, loss_a: float, loss_b: float,
                       lo: float, hi: float) -> str:
    pct = prob * 100
    lo_pp, hi_pp = lo * 100, hi * 100
    if prob >= 0.5:
        return (
            f"There is a {pct:.0f}% chance that B's true rate is higher than "
            f"A's. The difference is most plausibly between {lo_pp:+.2f} and "
            f"{hi_pp:+.2f} points. Shipping B risks losing about "
            f"{loss_b * 100:.3f} points on average if A is secretly better; "
            f"staying with A risks about {loss_a * 100:.3f} points."
        )
    return (
        f"There is only a {pct:.0f}% chance that B's true rate is higher "
        f"than A's. The difference is most plausibly between {lo_pp:+.2f} "
        f"and {hi_pp:+.2f} points. Staying with A risks losing about "
        f"{loss_a * 100:.3f} points on average if B is secretly better; "
        f"shipping B risks about {loss_b * 100:.3f} points."
    )


# --------------------------------------------------------------------------
# combined entry point
# --------------------------------------------------------------------------

def _validate(n_a: int, x_a: int, n_b: int, x_b: int) -> None:
    for n, x, name in ((n_a, x_a, "A"), (n_b, x_b, "B")):
        if n <= 0:
            raise ValueError(f"group {name}: visitors must be positive")
        if not 0 <= x <= n:
            raise ValueError(f"group {name}: conversions must lie in [0, n]")


def analyze(
    n_a: int, x_a: int, n_b: int, x_b: int,
    prior_alpha: float = 1.0, prior_beta: float = 1.0,
) -> ABAnalysis:
    return ABAnalysis(
        n_a=n_a, x_a=x_a, n_b=n_b, x_b=x_b,
        classic=classic_read(n_a, x_a, n_b, x_b),
        bayesian=bayesian_read(n_a, x_a, n_b, x_b, prior_alpha, prior_beta),
    )


# --------------------------------------------------------------------------
# decision rule used as ground truth for the LLM check (fixed in PLAN.md)
# --------------------------------------------------------------------------

def decision(prob_b_beats_a: float, loss_choose_a: float, loss_choose_b: float) -> str:
    """Ship B if it is very probably better and cheap to be wrong about;
    ship A symmetrically; otherwise keep testing."""
    if prob_b_beats_a >= 0.95 and loss_choose_b <= 0.002:
        return "ship_b"
    if prob_b_beats_a <= 0.05 and loss_choose_a <= 0.002:
        return "ship_a"
    return "keep_testing"
