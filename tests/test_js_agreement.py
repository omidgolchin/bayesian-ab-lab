"""The playground's JavaScript maths must agree with the Python calculator
on fixed cases (a spec requirement). Runs docs/abmath.js under Node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.bayesab.stats import analyze

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

CASES = [
    (100, 10, 100, 20),    # documented check case
    (2000, 200, 2000, 224),
    (447, 89, 460, 104),
    (60, 6, 58, 11),       # small sample
]

pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")


def _js_results() -> dict:
    script = (
        "const m = require(%s);\n"
        "const cases = %s;\n"
        "const out = {};\n"
        "for (const c of cases) { const r = m.analyze(c[0], c[1], c[2], c[3]);\n"
        "  out[c.join(',')] = { p: r.classic.pValue, prob: r.bayesian.probBBeatsA,\n"
        "    lossA: r.bayesian.expectedLossChooseA, lossB: r.bayesian.expectedLossChooseB,\n"
        "    ciLow: r.bayesian.diffCiLow, ciHigh: r.bayesian.diffCiHigh }; }\n"
        "console.log(JSON.stringify(out));\n"
    ) % (json.dumps(str(ROOT / "docs" / "abmath.js")), json.dumps(CASES))
    proc = subprocess.run([NODE, "-e", script], capture_output=True,
                          text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_js_matches_python():
    js = _js_results()
    for case in CASES:
        res = analyze(*case)
        got = js[",".join(str(v) for v in case)]
        assert got["p"] == pytest.approx(res.classic.p_value, abs=0.002)
        assert got["prob"] == pytest.approx(res.bayesian.prob_b_beats_a,
                                            abs=0.004)
        assert got["lossA"] == pytest.approx(
            res.bayesian.expected_loss_choose_a, abs=3e-4)
        assert got["lossB"] == pytest.approx(
            res.bayesian.expected_loss_choose_b, abs=3e-4)
        assert got["ciLow"] == pytest.approx(res.bayesian.diff_ci_low,
                                             abs=0.004)
        assert got["ciHigh"] == pytest.approx(res.bayesian.diff_ci_high,
                                              abs=0.004)
