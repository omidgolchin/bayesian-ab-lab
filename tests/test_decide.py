"""Tests for the decision layer (src/bayesab/decide.py and docs/decide.js)."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import chisquare, norm

from src.bayesab.decide import (always_valid_p, detectable_lift, equivalent,
                                sample_size_per_arm, srm_p_value)

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@pytest.mark.parametrize("n_a,n_b,share", [(10480, 9520, 0.5), (5000, 5050, 0.5), (3000, 7000, 0.7)])
def test_srm_matches_scipy(n_a, n_b, share):
    total = n_a + n_b
    expected = [total * (1 - share), total * share]
    assert srm_p_value(n_a, n_b, share) == pytest.approx(chisquare([n_a, n_b], expected).pvalue, rel=1e-9)


def test_srm_flags_a_broken_split():
    assert srm_p_value(10480, 9520) < 0.001
    assert srm_p_value(10020, 9980) > 0.5


def test_sample_size_textbook_case():
    # base 10%, +2 points, alpha 5% two-sided, 80% power: about 3,841 per arm
    assert sample_size_per_arm(0.10, 0.02) == 3841


def test_sample_size_grows_with_versions_and_power():
    two = sample_size_per_arm(0.05, 0.005)
    assert sample_size_per_arm(0.05, 0.005, versions=3) > two
    assert sample_size_per_arm(0.05, 0.005, power=0.9) > two


def test_detectable_lift_inverts_sample_size():
    n = sample_size_per_arm(0.042, 0.0021)
    assert detectable_lift(0.042, n) == pytest.approx(0.0021, rel=0.01)


def test_equivalence():
    assert equivalent(200000, 20000, 200000, 20050, margin=0.005)       # tiny diff, big n
    assert not equivalent(2000, 200, 2000, 205, margin=0.005)           # too uncertain
    assert not equivalent(200000, 20000, 200000, 21500, margin=0.005)   # real difference


def test_always_valid_p_is_valid_under_peeking():
    """A and B identical, checked 40 times: false alarms stay under 5%."""
    rng = np.random.default_rng(20261113)
    looks, every, sims, p = 40, 250, 2000, 0.10
    alarms = 0
    for _ in range(sims):
        a = np.cumsum(rng.random(looks * every) < p)
        b = np.cumsum(rng.random(looks * every) < p)
        for k in range(1, looks + 1):
            m = k * every
            if always_valid_p(m, int(a[m - 1]), m, int(b[m - 1]), tau=0.02) < 0.05:
                alarms += 1
                break
    assert alarms / sims < 0.05


def test_always_valid_p_finds_a_real_effect():
    assert always_valid_p(20000, 2000, 20000, 2400, tau=0.02) < 0.001


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_js_matches_python():
    cases = [(10000, 420, 10000, 498), (10480, 440, 9520, 455), (6200, 260, 6150, 302)]
    script = (
        "const D = require(%s);\nconst cases = %s;\nconst out = [];\n"
        "for (const c of cases) out.push({ srm: D.srmPValue(c[0], c[2], 0.5),"
        " av: D.alwaysValidP(c[0], c[1], c[2], c[3], 0.002),"
        " n: D.sampleSizePerArm(c[1] / c[0], 0.002, 0.05, 0.8, 2),"
        " eq: D.equivalent(c[0], c[1], c[2], c[3], 0.01) });\n"
        "console.log(JSON.stringify(out));\n"
    ) % (json.dumps(str(ROOT / "docs" / "decide.js")), json.dumps(cases))
    proc = subprocess.run([NODE, "-e", "globalThis.ABMath = require(%s);\n" % json.dumps(str(ROOT / "docs" / "abmath.js")) + script],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    js = json.loads(proc.stdout)
    for c, got in zip(cases, js):
        assert got["srm"] == pytest.approx(srm_p_value(c[0], c[2]), abs=1e-6)
        assert got["av"] == pytest.approx(always_valid_p(*c, tau=0.002), rel=1e-6)
        assert got["n"] == sample_size_per_arm(c[1] / c[0], 0.002)
        assert got["eq"] == equivalent(*c, margin=0.01)


def test_js_peeking_table_matches_simulation_results():
    data = json.loads((ROOT / "docs" / "data" / "peeking.json").read_text())
    js = (ROOT / "docs" / "decide.js").read_text()
    start = js.index("PEEK_FPR = [") + len("PEEK_FPR = ")
    table = json.loads(js[start: js.index("]", start) + 1])
    assert table == data["classic_fpr"]
