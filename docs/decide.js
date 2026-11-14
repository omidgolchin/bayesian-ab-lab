/* Decision layer of the A/B Test Decision Tool. Mirrors src/bayesab/decide.py
 * (checked by tests/test_decide.py). Uses ABMath (abmath.js) for the classic
 * and Bayesian reads.
 */
(function (global) {
  "use strict";
  var AB = global.ABMath || (typeof require !== "undefined" ? require("./abmath.js") : null);

  // Simulated false-alarm rate of a plain p < 0.05 test checked k times
  // (k = 1..40; A and B identical; 5,000 simulated tests; results/ in the repo).
  var PEEK_FPR = [0.0448, 0.0782, 0.0982, 0.1168, 0.1324, 0.1464, 0.157, 0.1682, 0.1748, 0.1808, 0.1886, 0.1964, 0.201, 0.2054, 0.2098, 0.2158, 0.221, 0.2262, 0.23, 0.2338, 0.2394, 0.2416, 0.2464, 0.2498, 0.2528, 0.2566, 0.2602, 0.2626, 0.2654, 0.2676, 0.2716, 0.2748, 0.2766, 0.2786, 0.2804, 0.284, 0.285, 0.2872, 0.289, 0.2912];

  function normCdf(z) { return AB._normCdf(z); }
  function normSf(z) { return 1 - normCdf(z); }
  function normInv(p) { // Acklam's rational approximation, |error| < 1.2e-9
    var a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
    var b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
    var c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
    var d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
    var q, r, pl = 0.02425;
    if (p < pl) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    if (p > 1 - pl) { q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    q = p - 0.5; r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }

  function srmPValue(nA, nB, shareB) {
    var total = nA + nB, eB = total * shareB, eA = total - eB;
    var stat = Math.pow(nA - eA, 2) / eA + Math.pow(nB - eB, 2) / eB;
    return 2 * normSf(Math.sqrt(stat));
  }
  function alwaysValidP(nA, xA, nB, xB, tau) {
    var rA = xA / nA, rB = xB / nB;
    var v = rA * (1 - rA) / nA + rB * (1 - rB) / nB;
    if (!(v > 0) || !(tau > 0)) return 1;
    var d = rB - rA, t2 = tau * tau;
    var logL = 0.5 * Math.log(v / (v + t2)) + t2 * d * d / (2 * v * (v + t2));
    return Math.min(1, Math.exp(-logL));
  }
  function ci90(nA, xA, nB, xB) {
    var rA = xA / nA, rB = xB / nB;
    var se = Math.sqrt(rA * (1 - rA) / nA + rB * (1 - rB) / nB), z = normInv(0.95);
    return [rB - rA - z * se, rB - rA + z * se];
  }
  function equivalent(nA, xA, nB, xB, margin) {
    var ci = ci90(nA, xA, nB, xB);
    return -margin < ci[0] && ci[1] < margin;
  }
  function sampleSizePerArm(p1, mdeAbs, alpha, power, versions) {
    alpha = alpha == null ? 0.05 : alpha; power = power == null ? 0.8 : power;
    var a = alpha / Math.max(1, (versions || 2) - 1), p2 = p1 + mdeAbs;
    if (!(p1 > 0 && p1 < 1 && p2 > 0 && p2 < 1) || mdeAbs === 0) return NaN;
    var pBar = (p1 + p2) / 2, zA = normInv(1 - a / 2), zB = normInv(power);
    var num = Math.pow(zA * Math.sqrt(2 * pBar * (1 - pBar)) + zB * Math.sqrt(p1 * (1 - p1) + p2 * (1 - p2)), 2);
    return Math.ceil(num / (mdeAbs * mdeAbs));
  }
  function detectableLift(p1, nPerArm, alpha, power, versions) {
    var lo = 1e-6, hi = Math.min(1 - p1, 0.999) - 1e-6, i;
    for (i = 0; i < 80; i++) {
      var mid = (lo + hi) / 2;
      if (sampleSizePerArm(p1, mid, alpha, power, versions) > nPerArm) lo = mid; else hi = mid;
    }
    return hi;
  }
  function peekFpr(k) {
    if (k <= 1) return 0.05;
    if (k > PEEK_FPR.length) return null;
    return PEEK_FPR[k - 1];
  }

  /* The verdict. inp: { nA, xA, nB, xB, shareB, checks, days, mdeAbs,
   *   shipProb, lossFrac, priorA, priorB, alpha }
   * Rule: ship the leader only when (1) the split is sound, (2) the chance it
   * is better clears shipProb, (3) its expected loss is under lossFrac x the
   * smallest worthwhile difference, and (4) the frequentist evidence agrees
   * (p < alpha; the always-valid p when the test was checked more than once).
   * Otherwise: equivalence (TOST) -> stop; else keep testing. */
  function decide(inp) {
    var r = AB.analyze(inp.nA, inp.xA, inp.nB, inp.xB, inp.priorA, inp.priorB);
    var c = r.classic, b = r.bayesian;
    var alpha = inp.alpha || 0.05;
    var srmP = srmPValue(inp.nA, inp.nB, inp.shareB);
    var peeked = inp.checks > 1;
    var avP = alwaysValidP(inp.nA, inp.xA, inp.nB, inp.xB, inp.mdeAbs);
    var evidenceP = peeked ? avP : c.pValue;
    var leadB = b.probBBeatsA >= 0.5;
    var probLead = leadB ? b.probBBeatsA : 1 - b.probBBeatsA;
    var lossLead = leadB ? b.expectedLossChooseB : b.expectedLossChooseA;
    var lossTol = inp.lossFrac * inp.mdeAbs;
    var eq = equivalent(inp.nA, inp.xA, inp.nB, inp.xB, inp.mdeAbs);
    var minArm = Math.min(inp.nA, inp.nB);
    var need = sampleSizePerArm(c.rateA > 0 && c.rateA < 1 ? c.rateA : 0.5, inp.mdeAbs, alpha, 0.8, 2);
    var perDay = inp.days > 0 ? (inp.nA + inp.nB) / inp.days : null;
    var small = Math.min(inp.xA, inp.nA - inp.xA, inp.xB, inp.nB - inp.xB) < 10;
    var state;
    if (srmP < 0.001) state = "srm";
    else if (probLead >= inp.shipProb && lossLead <= lossTol && evidenceP < alpha && !small) state = leadB ? "ship_b" : "keep_a";
    else if (eq) state = "equivalent";
    else state = "keep_testing";
    return {
      state: state, classic: c, bayes: b, srmP: srmP, peeked: peeked, alwaysValidP: avP,
      evidenceP: evidenceP, leadB: leadB, probLead: probLead, lossLead: lossLead, lossTol: lossTol,
      equivalent: eq, ci90: ci90(inp.nA, inp.xA, inp.nB, inp.xB), needPerArm: need,
      moreNeeded: Math.max(0, need - minArm), perDay: perDay, small: small,
      peekFpr: peekFpr(inp.checks)
    };
  }

  var api = { decide: decide, srmPValue: srmPValue, alwaysValidP: alwaysValidP, equivalent: equivalent,
    ci90: ci90, sampleSizePerArm: sampleSizePerArm, detectableLift: detectableLift, peekFpr: peekFpr,
    normInv: normInv, PEEK_FPR: PEEK_FPR };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.Decide = api;
})(typeof window !== "undefined" ? window : globalThis);
