/* Bayesian A/B Lab playground logic. All maths comes from abmath.js;
 * the other tabs render JSON precomputed by `python -m src.bayesab.analyze`.
 */
(function () {
  "use strict";
  var A_COLOR = "#2563eb", B_COLOR = "#d97706";

  // ---- tabs ---------------------------------------------------------------
  var tabBtns = document.querySelectorAll("#tabs button");
  tabBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      tabBtns.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      document.querySelectorAll("section.tab").forEach(function (s) {
        s.classList.remove("active");
      });
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    });
  });

  // ---- tiny chart helpers (Chart.js if the CDN loaded, else hand-drawn) ---
  function lineChart(canvas, series, opts) {
    opts = opts || {};
    if (window.Chart) {
      new Chart(canvas, {
        type: "line",
        data: { datasets: series.map(function (s) {
          return { label: s.label, data: s.points.map(function (p) { return { x: p[0], y: p[1] }; }),
                   borderColor: s.color, backgroundColor: s.color, pointRadius: s.dash ? 3 : 0,
                   borderDash: s.dash ? [5, 4] : [], tension: 0.15, fill: !!s.fill };
        }) },
        options: { responsive: false, animation: false,
          scales: { x: { type: "linear", title: { display: !!opts.xTitle, text: opts.xTitle } },
                    y: { title: { display: !!opts.yTitle, text: opts.yTitle } } },
          plugins: { legend: { display: series.length > 1 } } }
      });
      return;
    }
    drawFallback(canvas, series, opts);
  }
  function drawFallback(canvas, series, opts) {
    var dpr = window.devicePixelRatio || 1;
    var W = canvas.clientWidth || 600, H = 260;
    canvas.width = W * dpr; canvas.height = H * dpr;
    var ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
    var xs = [], ys = [];
    series.forEach(function (s) { s.points.forEach(function (p) { xs.push(p[0]); ys.push(p[1]); }); });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    var y0 = Math.min(0, Math.min.apply(null, ys)), y1 = Math.max.apply(null, ys) * 1.08 || 1;
    var padL = opts.yTitle ? 62 : 44, padB = 22, padT = 8, padR = 8;
    function X(v) { return padL + (v - x0) / (x1 - x0) * (W - padL - padR); }
    function Y(v) { return H - padB - (v - y0) / (y1 - y0) * (H - padB - padT); }
    ctx.strokeStyle = "#d9dee6"; ctx.fillStyle = "#5b6572"; ctx.font = "11px sans-serif";
    for (var i = 0; i <= 4; i++) {
      var yv = y0 + (y1 - y0) * i / 4, yy = Y(yv);
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
      var tick = yv.toFixed(opts.yDigits == null ? 2 : opts.yDigits);
      ctx.fillText(tick, padL - ctx.measureText(tick).width - 5, yy + 3);
    }
    if (opts.yTitle) {
      ctx.save();
      ctx.translate(13, (padT + H - padB) / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = "center";
      ctx.fillText(opts.yTitle, 0, 0);
      ctx.restore();
    }
    series.forEach(function (s) {
      ctx.strokeStyle = s.color; ctx.fillStyle = s.color; ctx.lineWidth = 1.8;
      ctx.setLineDash(s.dash ? [5, 4] : []);
      ctx.beginPath();
      s.points.forEach(function (p, j) { j ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])); });
      ctx.stroke(); ctx.setLineDash([]);
      // A filled curve (a density) runs along zero at the right edge, so an
      // end label lands there as a stray mark; label it at its peak instead.
      // Plain lines keep the end label.
      var anchor = s.points[s.points.length - 1];
      if (s.fill) {
        for (var k = 0; k < s.points.length; k++) {
          if (s.points[k][1] > anchor[1]) anchor = s.points[k];
        }
      }
      var tw = ctx.measureText(s.label).width;
      var lx = s.fill
        ? Math.max(padL, Math.min(X(anchor[0]) - tw / 2, W - padR - tw))
        : Math.max(padL, Math.min(X(anchor[0]) - tw - 2, W - padR - tw));
      ctx.fillText(s.label, lx, Y(anchor[1]) - 6);
    });
  }

  function fmtPct(x, d) { return (100 * x).toFixed(d == null ? 2 : d) + "%"; }
  function fmtPp(x, d) { return (100 * x).toFixed(d == null ? 2 : d); }
  function fmtP(p) { return p < 0.001 ? "<0.001" : p.toFixed(3); }
  function loadJSON(name) {
    return fetch("data/" + name).then(function (r) {
      if (!r.ok) throw new Error(name); return r.json();
    });
  }

  // ---- calculator -----------------------------------------------------------
  var PRESETS = {
    cookie1: [44700, 20034, 45489, 20119],
    cookie7: [44700, 8502, 45489, 8279],
    check: [100, 10, 100, 20],
    trap: [60, 6, 58, 11]
  };
  var els = {};
  ["na", "xa", "nb", "xb", "pa", "pb"].forEach(function (id) { els[id] = document.getElementById(id); });

  function runCalc() {
    var nA = +els.na.value, xA = +els.xa.value, nB = +els.nb.value, xB = +els.xb.value;
    var pa = +els.pa.value || 1, pb = +els.pb.value || 1;
    if (!(nA > 0 && nB > 0 && xA >= 0 && xB >= 0 && xA <= nA && xB <= nB)) return;
    var r = ABMath.analyze(nA, xA, nB, xB, pa, pb);
    var c = r.classic, b = r.bayesian;
    document.getElementById("classic-out").innerHTML =
      "<table>" +
      "<tr><th></th><th>A</th><th>B</th></tr>" +
      "<tr><td>Rate</td><td class='num'>" + fmtPct(c.rateA) + "</td><td class='num'>" + fmtPct(c.rateB) + "</td></tr>" +
      "<tr><td>Difference (B − A)</td><td colspan='2' class='num'>" + fmtPp(c.diff) + " points</td></tr>" +
      "<tr><td>95% confidence interval</td><td colspan='2' class='num'>" + fmtPp(c.ciLow) + " to " + fmtPp(c.ciHigh) + " points</td></tr>" +
      "<tr><td>p-value</td><td colspan='2' class='num'>" + fmtP(c.pValue) + "</td></tr></table>";
    document.getElementById("classic-sentence").textContent = ABMath.classicSentence(c);
    document.getElementById("bayes-out").innerHTML =
      "<table>" +
      "<tr><th></th><th>A</th><th>B</th></tr>" +
      "<tr><td>Posterior mean rate</td><td class='num'>" + fmtPct(b.postA.mean) + "</td><td class='num'>" + fmtPct(b.postB.mean) + "</td></tr>" +
      "<tr><td>95% credible interval</td><td class='num'>" + fmtPct(b.postA.ciLow, 1) + "–" + fmtPct(b.postA.ciHigh, 1) +
        "</td><td class='num'>" + fmtPct(b.postB.ciLow, 1) + "–" + fmtPct(b.postB.ciHigh, 1) + "</td></tr>" +
      "<tr><td>P(B beats A)</td><td colspan='2' class='num'><b>" + fmtPct(b.probBBeatsA, 1) + "</b></td></tr>" +
      "<tr><td>Expected loss if you ship B</td><td colspan='2' class='num'>" + fmtPp(b.expectedLossChooseB, 3) + " points</td></tr>" +
      "<tr><td>Expected loss if you stay with A</td><td colspan='2' class='num'>" + fmtPp(b.expectedLossChooseA, 3) + " points</td></tr>" +
      "<tr><td>95% credible interval for the difference</td><td colspan='2' class='num'>" + fmtPp(b.diffCiLow) + " to " + fmtPp(b.diffCiHigh) + " points</td></tr></table>";
    document.getElementById("bayes-sentence").textContent = ABMath.bayesianSentence(b);
    var g = b.grid, ptsA = [], ptsB = [], step = Math.max(1, Math.floor(g.xs.length / 220));
    for (var i = 0; i < g.xs.length; i += step) { ptsA.push([g.xs[i], g.pdfA[i]]); ptsB.push([g.xs[i], g.pdfB[i]]); }
    var canvas = document.getElementById("posterior-chart");
    var parent = canvas.parentElement;
    var fresh = document.createElement("canvas");
    fresh.className = "chart"; fresh.id = "posterior-chart";
    parent.replaceChild(fresh, canvas);
    lineChart(fresh, [
      { label: "A", color: A_COLOR, points: ptsA, fill: true },
      { label: "B", color: B_COLOR, points: ptsB, fill: true }
    ], { yTitle: "density", yDigits: 0 });
  }
  Object.values(els).forEach(function (el) { el.addEventListener("input", runCalc); });
  document.querySelectorAll("[data-preset]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var p = PRESETS[btn.dataset.preset];
      els.na.value = p[0]; els.xa.value = p[1]; els.nb.value = p[2]; els.xb.value = p[3];
      runCalc();
    });
  });
  runCalc();

  // ---- Cookie Cats tab -------------------------------------------------------
  loadJSON("cookiecats.json").then(function (cc) {
    var counts = cc.counts, rows = "";
    [["retention_1", "1-day retention"], ["retention_7", "7-day retention"]].forEach(function (pair) {
      var key = pair[0], r = cc.metrics[key];
      rows += "<tr><td>" + pair[1] + "</td>" +
        "<td class='num'>" + fmtPct(r.rate_a) + "</td><td class='num'>" + fmtPct(r.rate_b) + "</td>" +
        "<td class='num'>" + fmtPp(r.diff) + "</td>" +
        "<td class='num'>" + fmtPp(r.classic_ci[0]) + " to " + fmtPp(r.classic_ci[1]) + "</td>" +
        "<td class='num'>" + fmtP(r.p_value) + "</td>" +
        "<td class='num'>" + fmtPct(r.prob_b_beats_a, 1) + "</td>" +
        "<td class='num'>" + fmtPp(r.bootstrap_ci[0]) + " to " + fmtPp(r.bootstrap_ci[1]) + "</td></tr>";
    });
    document.getElementById("cookie-out").innerHTML =
      "<table><tr><th>Metric</th><th>gate_30</th><th>gate_40</th><th>Difference (pts)</th>" +
      "<th>Classic 95% CI</th><th>p</th><th>P(40 beats 30)</th><th>Bootstrap 95% CI</th></tr>" +
      rows + "</table>" +
      "<p class='sentence'>" + cc.metrics.retention_7.classic_sentence + "</p>" +
      "<p class='sentence bayes'>" + cc.metrics.retention_7.bayesian_sentence + "</p>" +
      "<p class='small muted'>Counts: gate_30 n=" + counts.gate_30.n.toLocaleString() +
      ", gate_40 n=" + counts.gate_40.n.toLocaleString() + ".</p>";
    var canvas = document.getElementById("cookie-chart");
    var series = [];
    [["retention_1", "1-day"], ["retention_7", "7-day"]].forEach(function (pair, i) {
      var r = cc.metrics[pair[0]];
      series.push({ label: pair[1] + " classic CI", color: A_COLOR,
        points: [[r.classic_ci[0] * 100, i * 3 + 2], [r.classic_ci[1] * 100, i * 3 + 2]] });
      series.push({ label: pair[1] + " bootstrap CI", color: B_COLOR,
        points: [[r.bootstrap_ci[0] * 100, i * 3 + 1], [r.bootstrap_ci[1] * 100, i * 3 + 1]] });
    });
    lineChart(canvas, series, { xTitle: "difference (points)", yDigits: 0 });
  }).catch(function () {
    document.getElementById("cookie-out").innerHTML =
      "<p class='muted'>The computed analysis has not been generated yet.</p>";
  });

  // ---- Peeking tab -------------------------------------------------------------
  loadJSON("peeking.json").then(function (pk) {
    var idx = [0, 4, 9, pk.peeks.length - 1];
    var labels = ["1 look", "5 looks", "10 looks", pk.peeks.length + " looks"];
    var html = "";
    idx.forEach(function (k, i) {
      html += "<div><span class='small muted'>" + labels[i] + " — classic / Bayes</span><b>" +
        fmtPct(pk.classic_fpr[k], 1) + " / " + fmtPct(pk.bayes_fpr[k], 1) + "</b></div>";
    });
    document.getElementById("peek-kpis").innerHTML = html;
    var series = [
      { label: "classic: stop at p < 0.05", color: A_COLOR,
        points: pk.peeks.map(function (p, i) { return [p, pk.classic_fpr[i] * 100]; }) },
      { label: "Bayes: stop at expected loss < 0.05 pts", color: B_COLOR,
        points: pk.peeks.map(function (p, i) { return [p, pk.bayes_fpr[i] * 100]; }) },
      { label: "Armitage et al. 1969", color: "#666", dash: true,
        points: pk.armitage_1969.looks.map(function (p, i) { return [p, pk.armitage_1969.fpr[i] * 100]; }) }
    ];
    lineChart(document.getElementById("peek-chart"), series,
      { xTitle: "number of looks", yTitle: "false-positive rate (%)", yDigits: 0 });
  }).catch(function () {});

  // power calculator (Acklam's inverse-normal approximation)
  function normPpf(p) {
    var a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
             1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
    var b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
             6.680131188771972e+01, -1.328068155288572e+01];
    var c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
             -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
    var d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
             3.754408661907416e+00];
    var plow = 0.02425, q, r;
    if (p < plow) {
      q = Math.sqrt(-2 * Math.log(p));
      return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
             ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
    }
    if (p > 1 - plow) {
      q = Math.sqrt(-2 * Math.log(1 - p));
      return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
              ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
    }
    q = p - 0.5; r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  function runPower() {
    var base = +document.getElementById("pk-base").value / 100;
    var mde = +document.getElementById("pk-mde").value / 100;
    if (!(base > 0 && base < 1 && mde > 0)) return;
    var za = normPpf(0.975), zb = normPpf(0.8);
    var n = Math.ceil(Math.pow(za + zb, 2) *
      (base * (1 - base) + (base + mde) * (1 - base - mde)) / (mde * mde));
    document.getElementById("pk-n").value = n.toLocaleString();
  }
  ["pk-base", "pk-mde"].forEach(function (id) {
    document.getElementById(id).addEventListener("input", runPower);
  });
  runPower();

  // ---- Thompson tab ------------------------------------------------------------
  loadJSON("thompson.json").then(function (th) {
    function block(title, d) {
      var f = d.fixed, t = d.thompson;
      return "<h3 style='margin-top:14px'>" + title + "</h3><table>" +
        "<tr><th></th><th>Fixed 50/50</th><th>Thompson</th></tr>" +
        "<tr><td>Mean conversions</td><td class='num'>" + f.mean_conversions.toFixed(0) +
          "</td><td class='num'>" + t.mean_conversions.toFixed(0) + "</td></tr>" +
        "<tr><td>Regret vs oracle</td><td class='num'>" + f.regret_vs_oracle.toFixed(0) +
          "</td><td class='num'>" + t.regret_vs_oracle.toFixed(0) + "</td></tr>" +
        "<tr><td>Final read: confident &amp; right</td><td class='num'>" + fmtPct(f.confident_and_right, 1) +
          "</td><td class='num'>" + fmtPct(t.confident_and_right, 1) + "</td></tr>" +
        "<tr><td>Final read: confident &amp; wrong</td><td class='num'>" + fmtPct(f.confident_and_wrong, 1) +
          "</td><td class='num'>" + fmtPct(t.confident_and_wrong, 1) + "</td></tr></table>";
    }
    document.getElementById("thompson-out").innerHTML =
      block("True rates 10% vs 12% (B is better)", th.effect) +
      block("True rates 10% vs 10% (no difference — any confident read is wrong; " +
            "the 'right' row here means the run ended uncommitted, which is the honest result)",
            th.no_effect);
  }).catch(function () {});

  // ---- LLM check tab -------------------------------------------------------------
  loadJSON("llmcheck.json").then(function (data) {
    if (!data.summary || !data.summary.length) {
      document.getElementById("llm-out").innerHTML =
        "<p class='muted'>The check has not been run yet.</p>";
      return;
    }
    var rows = "";
    data.summary.forEach(function (s) {
      rows += "<tr><td>" + s.model + "</td><td>" + s.mode + "</td>" +
        "<td class='num'>" + s.format_ok + "/" + s.n + "</td>" +
        "<td class='num'>" + (s.decision_accuracy == null ? "—" :
          (s.decision_accuracy * 100).toFixed(0) + "% (" + s.decisions_correct + "/" + s.decisions_scored + ")") + "</td>" +
        "<td class='num'>" + (s.mean_prob_error_pp == null ? "—" : s.mean_prob_error_pp.toFixed(1)) + "</td>" +
        "<td class='num'>" + s.flags_hit + "/" + s.flags_scored + "</td></tr>";
    });
    document.getElementById("llm-out").innerHTML =
      "<table><tr><th>Model</th><th>Mode</th><th>Format ok</th><th>Decision accuracy</th>" +
      "<th>Mean probability error (pts)</th><th>Problems flagged</th></tr>" + rows + "</table>";
    var byItem = {};
    data.scores.forEach(function (s) {
      (byItem[s.item_id] = byItem[s.item_id] || []).push(s);
    });
    var irows = "";
    data.items.forEach(function (it) {
      var ss = byItem[it.id] || [];
      var cells = ss.map(function (s) {
        var mark = s.decision_correct == null ? "·" : (s.decision_correct ? "✓" : "✗");
        var short = s.model.split("/").pop();
        return "<span class='tag'>" + short + " · " + s.mode + " " + mark + "</span>";
      }).join(" ");
      irows += "<tr><td class='num'>" + it.id.replace("item", "#") + "</td>" +
        "<td>" + it.category.replace(/_/g, " ") + "</td>" +
        "<td class='num'>" + it.x_a + "/" + it.n_a + " vs " + it.x_b + "/" + it.n_b + "</td>" +
        "<td class='num'>" + fmtPct(it.prob_b_beats_a, 1) + "</td>" +
        "<td>" + it.ground_truth_decision.replace(/_/g, " ") + "</td><td>" + cells + "</td></tr>";
    });
    document.getElementById("llm-items").innerHTML =
      "<h3 style='margin-top:16px'>Item by item</h3>" +
      "<table><tr><th>#</th><th>Situation</th><th>A vs B</th><th>P(B beats A)</th><th>Ground truth</th><th>Model marks</th></tr>" +
      irows + "</table>";
  }).catch(function () {});
})();
