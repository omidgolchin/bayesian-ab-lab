/* Bayesian A/B maths for the playground, mirroring src/bayesab/stats.py.
 *
 * The Python side computes P(B beats A), expected losses and the credible
 * interval for the difference by exact formulas and quadrature. Here the
 * same quantities are computed by trapezoid integration on a grid fitted
 * to the two posteriors, which agrees with the Python values to within
 * plotting accuracy (checked by tests/test_js_agreement.py on fixed cases).
 *
 * No dependencies; also loadable from Node for the agreement test.
 */
(function (global) {
  "use strict";

  // ---- special functions -------------------------------------------------
  function lgamma(z) { // Lanczos approximation
    var c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028,
      771.32342877765313, -176.61502916214059, 12.507343278686905,
      -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
    if (z < 0.5) {
      return Math.log(Math.PI / Math.sin(Math.PI * z)) - lgamma(1 - z);
    }
    z -= 1;
    var x = c[0], i, t = z + 7.5;
    for (i = 1; i < c.length; i++) x += c[i] / (z + i);
    return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
  }
  function betaln(a, b) { return lgamma(a) + lgamma(b) - lgamma(a + b); }
  function normCdf(z) { // Abramowitz & Stegun 7.1.26 erf approximation
    var x = Math.abs(z) / Math.SQRT2;
    var t = 1 / (1 + 0.3275911 * x);
    var poly = (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
      - 0.284496736) * t + 0.254829592) * t;
    var erf = 1 - poly * Math.exp(-x * x);
    var cdf = 0.5 * (1 + erf);
    return z < 0 ? 1 - cdf : cdf;
  }
  function normSf(z) { return 1 - normCdf(z); }

  // ---- grids ---------------------------------------------------------------
  function posteriorGrid(aA, bA, aB, bB, points) {
    var mA = aA / (aA + bA), mB = aB / (aB + bB);
    var sA = Math.sqrt(mA * (1 - mA) / (aA + bA + 1));
    var sB = Math.sqrt(mB * (1 - mB) / (aB + bB + 1));
    var s = Math.max(sA, sB);
    var lo = Math.max(0, Math.min(mA, mB) - 10 * s);
    var hi = Math.min(1, Math.max(mA, mB) + 10 * s);
    if (hi - lo < 1e-9) { lo = Math.max(0, lo - 0.01); hi = Math.min(1, hi + 0.01); }
    var xs = new Float64Array(points), i, x;
    for (i = 0; i < points; i++) xs[i] = lo + (hi - lo) * i / (points - 1);
    function pdf(a, b) {
      var out = new Float64Array(points), lb = betaln(a, b), v;
      for (i = 0; i < points; i++) {
        x = xs[i];
        if (x <= 0 || x >= 1) { out[i] = 0; continue; }
        v = Math.exp((a - 1) * Math.log(x) + (b - 1) * Math.log(1 - x) - lb);
        out[i] = isFinite(v) ? v : 0;
      }
      return out;
    }
    return { xs: xs, pdfA: pdf(aA, bA), pdfB: pdf(aB, bB) };
  }
  function trapzCum(xs, ys) { // cumulative trapezoid, normalised to end at 1
    var n = xs.length, out = new Float64Array(n), acc = 0, i;
    for (i = 1; i < n; i++) {
      acc += 0.5 * (ys[i] + ys[i - 1]) * (xs[i] - xs[i - 1]);
      out[i] = acc;
    }
    if (acc > 0) for (i = 0; i < n; i++) out[i] /= acc;
    out[n - 1] = 1;
    return out;
  }
  function trapz(xs, ys) {
    var acc = 0, i;
    for (i = 1; i < xs.length; i++) acc += 0.5 * (ys[i] + ys[i - 1]) * (xs[i] - xs[i - 1]);
    return acc;
  }
  function quantile(xs, cdf, q) {
    var i;
    for (i = 1; i < xs.length; i++) {
      if (cdf[i] >= q) {
        var span = cdf[i] - cdf[i - 1] || 1e-12;
        return xs[i - 1] + (xs[i] - xs[i - 1]) * (q - cdf[i - 1]) / span;
      }
    }
    return xs[xs.length - 1];
  }

  // ---- the calculator -------------------------------------------------------
  function analyze(nA, xA, nB, xB, priorAlpha, priorBeta) {
    priorAlpha = priorAlpha == null ? 1 : priorAlpha;
    priorBeta = priorBeta == null ? 1 : priorBeta;
    var rateA = xA / nA, rateB = xB / nB, diff = rateB - rateA;
    var pooled = (xA + xB) / (nA + nB);
    var sePooled = Math.sqrt(pooled * (1 - pooled) * (1 / nA + 1 / nB));
    var z = sePooled > 0 ? diff / sePooled : 0;
    var pValue = 2 * normSf(Math.abs(z));
    var se = Math.sqrt(rateA * (1 - rateA) / nA + rateB * (1 - rateB) / nB);
    var classic = {
      rateA: rateA, rateB: rateB, diff: diff, pValue: pValue,
      ciLow: diff - 1.959964 * se, ciHigh: diff + 1.959964 * se
    };

    var aA = priorAlpha + xA, bA = priorBeta + nA - xA;
    var aB = priorAlpha + xB, bB = priorBeta + nB - xB;
    var g = posteriorGrid(aA, bA, aB, bB, 1601);
    var cdfA = trapzCum(g.xs, g.pdfA), cdfB = trapzCum(g.xs, g.pdfB);
    var i, integrand = new Float64Array(g.xs.length);
    for (i = 0; i < g.xs.length; i++) integrand[i] = g.pdfB[i] * cdfA[i];
    var probB = trapz(g.xs, integrand);
    for (i = 0; i < g.xs.length; i++) integrand[i] = cdfB[i] * (1 - cdfA[i]);
    var lossB = trapz(g.xs, integrand); // E[(pA - pB)+]: cost of choosing B
    for (i = 0; i < g.xs.length; i++) integrand[i] = cdfA[i] * (1 - cdfB[i]);
    var lossA = trapz(g.xs, integrand); // E[(pB - pA)+]: cost of choosing A

    // distribution of the difference, on its own grid:
    // F_diff(d) = P(pB - pA <= d) = E over pA of F_B(pA + d)
    var dLo = g.xs[0] - g.xs[g.xs.length - 1], dHi = -dLo;
    var nd = 1201, dXs = new Float64Array(nd);
    var step = (dHi - dLo) / (nd - 1), j, k;
    var dCdf = new Float64Array(nd);
    function cdfBat(v) {
      if (v <= g.xs[0]) return 0;
      if (v >= g.xs[g.xs.length - 1]) return 1;
      var idx = (v - g.xs[0]) / (g.xs[1] - g.xs[0]);
      var i0 = Math.min(Math.floor(idx), g.xs.length - 2);
      return cdfB[i0] + (cdfB[i0 + 1] - cdfB[i0]) * (idx - i0);
    }
    for (j = 0; j < nd; j++) {
      var d = dLo + step * j, s = 0;
      for (k = 0; k < g.xs.length; k++) s += g.pdfA[k] * cdfBat(g.xs[k] + d);
      dCdf[j] = s * (g.xs[1] - g.xs[0]); // trapezoid sum against the pA grid
      dXs[j] = d;
    }
    // normalise the diff CDF to be non-decreasing and end at 1
    var mx = 0;
    for (j = 0; j < nd; j++) { mx = Math.max(mx, dCdf[j]); dCdf[j] = mx; }
    if (mx > 0) for (j = 0; j < nd; j++) dCdf[j] /= mx;

    var bayes = {
      postA: { alpha: aA, beta: bA, mean: aA / (aA + bA),
        ciLow: quantile(g.xs, cdfA, 0.025), ciHigh: quantile(g.xs, cdfA, 0.975) },
      postB: { alpha: aB, beta: bB, mean: aB / (aB + bB),
        ciLow: quantile(g.xs, cdfB, 0.025), ciHigh: quantile(g.xs, cdfB, 0.975) },
      probBBeatsA: Math.min(1, Math.max(0, probB)),
      expectedLossChooseA: lossA, expectedLossChooseB: lossB,
      diffCiLow: quantile(dXs, dCdf, 0.025), diffCiHigh: quantile(dXs, dCdf, 0.975),
      grid: { xs: Array.from(g.xs), pdfA: Array.from(g.pdfA), pdfB: Array.from(g.pdfB) }
    };
    return { classic: classic, bayesian: bayes };
  }

  function decision(prob, lossA, lossB) {
    if (prob >= 0.95 && lossB <= 0.002) return "ship_b";
    if (prob <= 0.05 && lossA <= 0.002) return "ship_a";
    return "keep_testing";
  }

  function pct(x, digits) { return (100 * x).toFixed(digits == null ? 2 : digits) + "%"; }
  function pp(x, digits) { return (100 * x).toFixed(digits == null ? 2 : digits); }

  function classicSentence(c) {
    var s = "B converted at " + pct(c.rateB) + " against A's " + pct(c.rateA) +
      " — a difference of " + pp(c.diff) + " points (95% confidence interval " +
      pp(c.ciLow) + " to " + pp(c.ciHigh) + ", p = " +
      (c.pValue < 0.001 ? "<0.001" : c.pValue.toFixed(3)) + "). ";
    if (c.pValue < 0.05) {
      s += "By the usual 0.05 rule this counts as statistically significant";
      s += c.ciLow > 0 ? ", and the interval stays above zero, so the classic read is: B looks better." :
        ", though the interval nearly touches zero.";
    } else {
      s += "By the usual 0.05 rule this is not statistically significant, so the classic read is: not enough evidence to call it";
      s += c.ciHigh < 0 ? " — and what evidence there is points to A." : ".";
    }
    return s;
  }
  function bayesianSentence(b) {
    var leader = b.probBBeatsA >= 0.5 ? "B" : "A";
    var probLeader = leader === "B" ? b.probBBeatsA : 1 - b.probBBeatsA;
    var lossLeader = leader === "B" ? b.expectedLossChooseB : b.expectedLossChooseA;
    var s = "There is a " + pp(probLeader, 1) + "% probability that " + leader +
      " has the higher true rate. Shipping " + leader + " now carries an expected loss of " +
      pp(lossLeader, 3) + " points of conversion if that is wrong; the 95% credible interval " +
      "for the difference (B minus A) is " + pp(b.diffCiLow) + " to " + pp(b.diffCiHigh) + " points. ";
    var d = decision(b.probBBeatsA, b.expectedLossChooseA, b.expectedLossChooseB);
    if (d === "ship_b") s += "That clears this lab's bar (95% probability, expected loss under 0.2 points): ship B.";
    else if (d === "ship_a") s += "That clears this lab's bar (95% probability, expected loss under 0.2 points): keep A and drop B.";
    else s += "That does not clear this lab's bar (95% probability and expected loss under 0.2 points), so the Bayesian read is: keep testing.";
    return s;
  }

  var api = { analyze: analyze, decision: decision, classicSentence: classicSentence,
    bayesianSentence: bayesianSentence, _lgamma: lgamma, _normCdf: normCdf };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.ABMath = api;
})(typeof window !== "undefined" ? window : globalThis);
