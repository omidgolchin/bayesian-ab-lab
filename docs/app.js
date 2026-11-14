/* A/B Test Decision Tool: page logic. Math lives in abmath.js and decide.js. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var F = Tool.fmt;

  var DEFAULTS = {
    mode: "analyze",
    nA: 10000, xA: 420, nB: 10000, xB: 498, checks: 1, days: 14, share: 50, mde: 5, mdeUnit: "rel", value: "",
    shipProb: 95, lossFrac: 10, prior: "flat", alpha: 5,
    pRate: 4.2, pMde: 5, pMdeUnit: "rel", pTraffic: 20000, pVersions: 2, pPower: 0.8, pAlpha: 5
  };
  var EXAMPLES = [
    { label: "A clear win", v: { nA: 10000, xA: 420, nB: 10000, xB: 498, checks: 1, days: 14, share: 50, mde: 5, mdeUnit: "rel", value: 40 } },
    { label: "Checked every day (peeking)", v: { nA: 6200, xA: 250, nB: 6150, xB: 302, checks: 12, days: 12, share: 50, mde: 10, mdeUnit: "rel", value: "" } },
    { label: "Broken traffic split", v: { nA: 10480, xA: 440, nB: 9520, xB: 455, checks: 1, days: 14, share: 50, mde: 5, mdeUnit: "rel", value: "" } },
    { label: "Too early to tell", v: { nA: 1200, xA: 50, nB: 1180, xB: 58, checks: 1, days: 3, share: 50, mde: 5, mdeUnit: "rel", value: "" } },
    { label: "Small-sample trap", v: { nA: 60, xA: 6, nB: 58, xB: 11, checks: 1, days: 2, share: 50, mde: 10, mdeUnit: "rel", value: "" } },
    { label: "Cookie Cats: gate at level 30 vs 40, 1-day retention", v: { nA: 44700, xA: 20034, nB: 45489, xB: 20119, checks: 1, days: "", share: 50, mde: 1, mdeUnit: "rel", value: "" } },
    { label: "Cookie Cats: gate at level 30 vs 40, 7-day retention", v: { nA: 44700, xA: 8502, nB: 45489, xB: 8279, checks: 1, days: "", share: 50, mde: 2, mdeUnit: "rel", value: "" } }
  ];
  var IDS_A = ["nA", "xA", "nB", "xB", "checks", "days", "share", "mde", "mdeUnit", "value", "shipProb", "lossFrac", "prior", "alpha"];
  var IDS_P = ["pRate", "pMde", "pMdeUnit", "pTraffic", "pVersions", "pPower", "pAlpha"];
  var state = Tool.readParams(DEFAULTS);
  var last = null, lastPlan = null;

  /* ---------- wiring ---------- */
  function setInputs(v) {
    Object.keys(v).forEach(function (k) { var e = $(k); if (e) e.value = v[k] === null ? "" : v[k]; });
  }
  setInputs(state);
  EXAMPLES.forEach(function (ex, i) { var o = document.createElement("option"); o.value = i; o.textContent = ex.label; $("example").appendChild(o); });
  $("example").addEventListener("change", function () {
    if (this.value === "") return;
    setInputs(EXAMPLES[+this.value].v);
    document.querySelectorAll(".field.filled").forEach(function (f) { f.classList.remove("filled"); });
    this.value = ""; runAnalyze();
  });
  IDS_A.forEach(function (id) { $(id).addEventListener("input", debounce(runAnalyze, 120)); $(id).addEventListener("change", runAnalyze); });
  IDS_P.forEach(function (id) { $(id).addEventListener("input", debounce(runPlan, 120)); $(id).addEventListener("change", runPlan); });
  function setMode(m) {
    state.mode = m;
    $("tab-analyze").classList.toggle("active", m === "analyze"); $("tab-analyze").setAttribute("aria-selected", m === "analyze");
    $("tab-plan").classList.toggle("active", m === "plan"); $("tab-plan").setAttribute("aria-selected", m === "plan");
    $("view-analyze").hidden = m !== "analyze"; $("view-plan").hidden = m !== "plan";
    if (m === "plan") runPlan(); else runAnalyze();
  }
  $("tab-analyze").addEventListener("click", function () { setMode("analyze"); });
  $("tab-plan").addEventListener("click", function () { setMode("plan"); });
  $("copyLink").addEventListener("click", function () { Tool.copy(location.href, $("toastA"), "Link copied: it opens with these numbers."); });
  $("pCopyLink").addEventListener("click", function () { Tool.copy(location.href, $("toastP"), "Link copied."); });
  $("copySummary").addEventListener("click", function () { if (last) Tool.copy(summaryText(), $("toastA"), "Summary copied."); });
  $("pCopySummary").addEventListener("click", function () { if (lastPlan) Tool.copy(planText(), $("toastP"), "Plan copied."); });
  window.addEventListener("resize", debounce(function () { if (state.mode === "plan") runPlan(); else runAnalyze(); }, 150));
  if (window.KitTheme) KitTheme.onChange(function () { setTimeout(function () { if (state.mode === "plan") runPlan(); else runAnalyze(); }, 0); });

  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }
  function num(id) { var v = $(id).value; return v === "" ? null : Number(v); }
  function fieldError(id, msg) {
    var f = $(id).closest(".field"); var e = f.querySelector(".err");
    f.classList.toggle("invalid", !!msg);
    if (msg) { if (!e) { e = document.createElement("div"); e.className = "err"; f.appendChild(e); } e.textContent = msg; }
    else if (e) e.remove();
  }

  /* ---------- AI assist ---------- */
  Tool.assist(Object.assign({}, window.ASSIST_CONFIG, {
    mount: $("assistMount"), toggle: $("assistToggle"),
    apply: function (vals) {
      document.querySelectorAll(".field.filled").forEach(function (f) { f.classList.remove("filled"); });
      Object.keys(vals).forEach(function (k) {
        var v = vals[k]; if (k === "nA" || k === "xA" || k === "nB" || k === "xB" || k === "checks" || k === "days") v = Math.round(v);
        $(k).value = v; $(k).closest(".field").classList.add("filled");
        if (k === "mde") $("mdeUnit").value = "rel";
      });
      runAnalyze();
    }
  }));

  /* ---------- analyze ---------- */
  function readAnalyze() {
    var v = { nA: num("nA"), xA: num("xA"), nB: num("nB"), xB: num("xB"), checks: num("checks") || 1, days: num("days"),
      share: num("share"), mde: num("mde"), mdeUnit: $("mdeUnit").value, value: num("value"),
      shipProb: num("shipProb"), lossFrac: num("lossFrac"), prior: $("prior").value, alpha: num("alpha") };
    var ok = true;
    function need(id, cond, msg) { var bad = !cond; fieldError(id, bad ? msg : ""); if (bad) ok = false; }
    need("nA", v.nA > 0 && Number.isInteger(v.nA), "Whole number above 0.");
    need("nB", v.nB > 0 && Number.isInteger(v.nB), "Whole number above 0.");
    need("xA", v.xA !== null && v.xA >= 0 && Number.isInteger(v.xA) && (v.nA === null || v.xA <= v.nA), "Between 0 and the visitors.");
    need("xB", v.xB !== null && v.xB >= 0 && Number.isInteger(v.xB) && (v.nB === null || v.xB <= v.nB), "Between 0 and the visitors.");
    need("share", v.share > 0 && v.share < 100, "Between 1 and 99.");
    need("mde", v.mde > 0, "Above 0.");
    need("checks", v.checks >= 1 && Number.isInteger(v.checks), "1 or more.");
    need("shipProb", v.shipProb >= 50 && v.shipProb < 100, "50 to 99.9.");
    need("lossFrac", v.lossFrac > 0 && v.lossFrac <= 100, "1 to 100.");
    need("alpha", v.alpha > 0 && v.alpha < 50, "0.1 to 20.");
    fieldError("days", v.days !== null && v.days < 0 ? "0 or more." : "");
    if (v.xA !== null && v.nA && v.xA === 0 && v.xB === 0) { fieldError("xA", "Need at least one conversion overall."); ok = false; }
    return ok ? v : null;
  }
  function runAnalyze() {
    var v = readAnalyze();
    Object.assign(state, v || {}); state.mode = "analyze";
    var urlState = {}; IDS_A.forEach(function (k) { urlState[k] = $(k).value; }); urlState.mode = "analyze";
    Tool.writeParams(urlState);
    if (!v) { $("vTitle").textContent = "Check the highlighted inputs"; $("vBody").textContent = ""; $("verdict").className = "panel verdict v-neutral"; $("kpis").innerHTML = ""; $("checksA").innerHTML = ""; return; }
    var rateA = v.xA / v.nA, rateB = v.xB / v.nB;
    var base = rateA > 0 && rateA < 1 ? rateA : (v.xA + v.xB) / (v.nA + v.nB);
    var mdeAbs = v.mdeUnit === "rel" ? base * v.mde / 100 : v.mde / 100;
    var pr = priorParams(v);
    var d = Decide.decide({ nA: v.nA, xA: v.xA, nB: v.nB, xB: v.xB, shareB: v.share / 100, checks: v.checks, days: v.days,
      mdeAbs: mdeAbs, shipProb: v.shipProb / 100, lossFrac: v.lossFrac / 100, priorA: pr.a, priorB: pr.b, alpha: v.alpha / 100 });
    last = { v: v, d: d, mdeAbs: mdeAbs, rateA: rateA, rateB: rateB };
    renderVerdict(); renderKpis(); renderChecks(); renderDiffChart(); renderDetails();
  }
  function priorParams(v) {
    if (v.prior === "skeptical") {
      var pooled = (v.xA + v.xB) / (v.nA + v.nB), n0 = 1000;
      $("priorHint").textContent = "Both versions start as if each had already had 1,000 visitors converting at the overall rate (" + F.pct(pooled, 2) + "). Small samples then cannot produce big lifts on their own.";
      return { a: Math.max(0.5, n0 * pooled), b: Math.max(0.5, n0 * (1 - pooled)) };
    }
    $("priorHint").textContent = "Beta(1, 1): every conversion rate equally plausible before the test.";
    return { a: 1, b: 1 };
  }
  function rel(x) { return (x >= 0 ? "+" : "−") + Math.abs(100 * x).toFixed(1) + "%"; }
  function pts(x) { return (x >= 0 ? "+" : "−") + Math.abs(100 * x).toFixed(2) + " pts"; }
  function pEq(p) { return p < 0.001 ? "p < 0.001" : "p = " + p.toFixed(3); }
  function pFmt(p) { return p < 0.001 ? "< 0.001" : p.toFixed(3); }

  function renderVerdict() {
    var L = last, d = L.d, v = L.v, c = d.classic;
    var lift = L.rateA > 0 ? (L.rateB - L.rateA) / L.rateA : NaN;
    var lead = d.leadB ? "B" : "A", other = d.leadB ? "A" : "B";
    var title, body, cls;
    var peekNote = d.peeked && c.pValue < v.alpha / 100 && d.alwaysValidP >= v.alpha / 100
      ? " A plain p-value would call this significant (" + pEq(c.pValue) + "), but after " + v.checks + " checks that is not trustworthy: the always-valid p-value is " + pFmt(d.alwaysValidP) + "." : "";
    if (d.state === "srm") {
      title = "Don’t trust this test yet"; cls = "bad";
      body = "You planned " + v.share + "% of traffic for B but B got " + F.pct(v.nB / (v.nA + v.nB), 1) + " (" + pEq(d.srmP) + "). A split this far off almost always means a bug in assignment, redirects or tracking, and it can bias every number on this page. Find the cause before reading the result.";
    } else if (d.state === "ship_b" || d.state === "keep_a") {
      title = d.state === "ship_b" ? "Ship B" : "Keep A, drop B"; cls = "good";
      var leadLift = d.leadB ? (L.rateB - L.rateA) / L.rateA : (L.rateA - L.rateB) / L.rateB;
      body = lead + " converts at " + F.pct(d.leadB ? L.rateB : L.rateA, 2) + " vs " + F.pct(d.leadB ? L.rateA : L.rateB, 2) + " for " + other + " (+" + (100 * leadLift).toFixed(1) + "% relative). There is a " + F.pct(d.probLead, 1) + " chance " + lead + " is truly better, and if it is not, you give up " + lossWords(d.lossLead) + " on average, well under your tolerance." + (d.peeked ? " The evidence holds even after " + v.checks + " checks (always-valid " + pEq(d.alwaysValidP) + ")." : "");
    } else if (d.state === "equivalent") {
      title = "No meaningful difference: stop"; cls = "accent";
      body = "The difference is between " + pts(d.ci90[0]) + " and " + pts(d.ci90[1]) + " (90% interval), inside your ±" + (100 * L.mdeAbs).toFixed(2) + "-point band. Any real difference is too small to be worth acting on. Stop the test and decide on cost, design or strategy instead.";
    } else {
      title = "Keep testing"; cls = "warn";
      if (d.moreNeeded > 0 && isFinite(d.moreNeeded)) {
        var daysMore = d.perDay ? Math.ceil(2 * d.moreNeeded / d.perDay) : null;
        title = "Keep testing: about " + F.int(roundNice(d.moreNeeded)) + " more visitors per version";
        body = "Not enough evidence yet. To reliably detect a " + liftWords() + " lift you need about " + F.int(d.needPerArm) + " visitors per version; you have " + F.int(Math.min(v.nA, v.nB)) + "." + (daysMore ? " At your current traffic that is about " + daysMore + " more day" + (daysMore === 1 ? "" : "s") + "; round up to whole weeks." : "") + peekNote;
      } else {
        body = "You have reached the size needed to detect a " + liftWords() + " lift, and the result is still unclear: the true difference is probably smaller than that but not ruled out. Either decide on cost and judgment, or extend the test to detect a smaller lift." + peekNote;
      }
      if (d.small) body = "Too little data to trust any read: one version has fewer than 10 conversions (or non-conversions). " + body;
    }
    $("vTitle").textContent = title; $("vBody").textContent = body;
    $("verdict").className = "panel verdict v-" + cls;
    L.title = title; L.body = body;
  }
  function lossWords(x) { return 100 * x < 0.001 ? "almost nothing (under 0.001 points)" : "about " + (100 * x).toFixed(3) + " points"; }
  function liftWords() { var v = last.v; return v.mdeUnit === "rel" ? v.mde + "% relative (" + (100 * last.mdeAbs).toFixed(2) + "-point)" : v.mde + "-point"; }
  function roundNice(x) { var p = Math.pow(10, Math.max(0, Math.floor(Math.log10(x)) - 1)); return Math.ceil(x / p) * p; }

  function renderKpis() {
    var L = last, d = L.d, c = d.classic;
    var lift = L.rateA > 0 ? (L.rateB - L.rateA) / L.rateA : NaN;
    var items = [
      [isFinite(lift) ? rel(lift) : "–", "lift of B (relative)"],
      [pts(c.diff).replace(" pts", ""), "difference (points)"],
      [F.pct(d.bayes.probBBeatsA, 1), "chance B is better"],
      [pFmt(d.evidenceP), d.peeked ? "always-valid p-value" : "p-value"]
    ];
    if (L.v.value) {
      var per10k = (L.rateB - L.rateA) * 10000 * L.v.value;
      items.push([(per10k >= 0 ? "+" : "") + F.money(per10k), "value of B per 10,000 visitors"]);
    }
    $("kpis").innerHTML = items.map(function (it) { return '<div class="kpi"><span class="k-val">' + it[0] + '</span><span class="k-lbl">' + it[1] + "</span></div>"; }).join("");
  }

  function renderChecks() {
    var L = last, d = L.d, v = L.v, out = [];
    var shareObs = v.nB / (v.nA + v.nB);
    out.push(d.srmP < 0.001
      ? ["fail", "MISMATCH", "Traffic split", "Planned " + v.share + "% to B, got " + F.pct(shareObs, 1) + " (" + pEq(d.srmP) + "). Usually a tracking or assignment bug."]
      : ["ok", "OK", "Traffic split", F.pct(shareObs, 1) + " to B, consistent with your planned " + v.share + "%."]);
    if (v.checks <= 1) out.push(["ok", "OK", "Peeking", "Read once, so the plain p-value means what it says."]);
    else {
      var f = d.peekFpr;
      out.push(["warn", "ADJUSTED", "Peeking", "Checked " + v.checks + " times. A plain p-value would be fooled " + (f ? "about " + Math.round(100 * f) + "%" : "nearly 30%") + " of the time instead of 5%, so this read uses the always-valid p-value (" + pFmt(d.alwaysValidP) + ")."]);
    }
    out.push(d.small
      ? ["warn", "SMALL", "Sample size", "Under 10 conversions or non-conversions in a version: intervals and p-values are unreliable here."]
      : ["ok", "OK", "Sample size", "Enough conversions in both versions for the approximations used."]);
    if (v.days === null || v.days === 0) out.push(["info", "ADD", "Test length", "Add the days it ran to check for full weekly cycles."]);
    else if (v.days < 7) out.push(["warn", "SHORT", "Test length", v.days + " day" + (v.days === 1 ? "" : "s") + ": less than a full week, so weekday mix and novelty effects are not covered."]);
    else if (v.days % 7 !== 0) out.push(["info", "NOTE", "Test length", v.days + " days is not whole weeks: some weekdays count twice. Prefer ending on a full week."]);
    else out.push(["ok", "OK", "Test length", v.days + " days: whole weeks, so every weekday is equally represented."]);
    $("checksA").innerHTML = out.map(function (c) {
      return '<div class="check is-' + c[0] + '"><span class="badge">' + c[1] + '</span><div><span class="c-name">' + c[2] + '.</span> <span class="c-text">' + c[3] + "</span></div></div>";
    }).join("");
    L.checks = out;
  }

  function renderDiffChart() {
    var L = last, d = L.d, host = $("diffChart");
    var c = d.classic, b = d.bayes, m = L.mdeAbs;
    var rows = [
      { label: "95% interval (classic)", lo: c.ciLow, hi: c.ciHigh, mid: c.diff, color: "accent" },
      { label: "95% credible (Bayesian)", lo: b.diffCiLow, hi: b.diffCiHigh, mid: b.postB.mean - b.postA.mean, color: "series2" }
    ];
    var lo = Math.min(-m * 1.4, rows[0].lo, rows[1].lo), hi = Math.max(m * 1.4, rows[0].hi, rows[1].hi);
    var pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    host.innerHTML = "";
    var W = Math.max(280, host.clientWidth || 600), narrow = W < 520, H = narrow ? 200 : 168;
    var ml = narrow ? 12 : 170, mr = 16, top = narrow ? 42 : 30;
    var NS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Difference between B and A with intervals"); host.appendChild(svg);
    function X(x) { return ml + (x - lo) / (hi - lo) * (W - ml - mr); }
    function add(n, a) { var e = document.createElementNS(NS, n); Object.keys(a).forEach(function (k) { e.setAttribute(k, a[k]); }); svg.appendChild(e); return e; }
    function txt(x, y, s, anchor, cls) { var t = add("text", { x: x, y: y, "text-anchor": anchor || "start" }); if (cls) t.setAttribute("class", cls); t.textContent = s; return t; }
    var css = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };
    var axisY = H - 40;
    add("rect", { x: X(-m), y: top - 8, width: X(m) - X(-m), height: axisY - top + 8, fill: css("--good"), opacity: 0.1 });
    txt(narrow ? ml : (X(-m) + X(m)) / 2, narrow ? 14 : top - 12, (narrow ? "Shaded: " : "") + "too small to matter (±" + (100 * m).toFixed(2) + " pts)", narrow ? "start" : "middle", "title");
    add("line", { x1: X(0), x2: X(0), y1: top - 8, y2: axisY, stroke: css("--fg"), "stroke-width": 1.2 });
    rows.forEach(function (r, i) {
      var y = top + (narrow ? 26 : 22) + i * (narrow ? 50 : 36);
      if (narrow) txt(ml, y - 12, r.label, "start", "halo");
      else txt(ml - 10, y + 4, r.label, "end");
      var col = css(r.color === "accent" ? "--accent" : "--series-2");
      add("line", { x1: X(r.lo), x2: X(r.hi), y1: y, y2: y, stroke: col, "stroke-width": 6, "stroke-linecap": "round", opacity: 0.85 });
      add("circle", { cx: X(r.mid), cy: y, r: 5.5, fill: css("--card"), stroke: col, "stroke-width": 2.5 });
    });
    add("line", { x1: ml, x2: W - mr, y1: axisY, y2: axisY, stroke: css("--muted") });
    Tool.niceTicks(lo, hi, narrow ? 4 : 7).forEach(function (t) {
      add("line", { x1: X(t), x2: X(t), y1: axisY, y2: axisY + 4, stroke: css("--muted") });
      txt(X(t), axisY + 16, (t > 0 ? "+" : t < 0 ? "−" : "") + Math.abs(100 * t).toFixed(Math.abs(hi - lo) < 0.02 ? 2 : 1), "middle");
    });
    txt((ml + W - mr) / 2, axisY + 34, "B minus A, in percentage points", "middle", "title");
    var c2 = d.classic;
    $("diffCaption").textContent = c2.ciLow > m ? "The whole interval is above the band: B's gain is both real and large enough to matter." :
      c2.ciHigh < -m ? "The whole interval is below the band: B is worse by a margin that matters." :
      d.equivalent ? "The interval sits inside the band: whatever the true difference is, it is too small to act on." :
      c2.ciLow > 0 ? "The interval is above zero, so B is better; its low end reaches into the shaded band, so the true gain could be smaller than the lift you care about. Best estimate: " + pts(c2.diff) + "." :
      c2.ciHigh < 0 ? "The interval is below zero, so B is worse; its high end reaches into the shaded band, so the true loss could be small. Best estimate: " + pts(c2.diff) + "." :
      "The interval crosses zero: the data are consistent with B being better, worse or the same.";
  }

  function renderDetails() {
    var L = last, d = L.d, c = d.classic, b = d.bayes;
    $("tClassic").innerHTML = rowsHtml([
      ["Conversion rate", F.pct(c.rateA, 2) + " → " + F.pct(c.rateB, 2)],
      ["Difference (B − A)", pts(c.diff)],
      ["95% confidence interval", pts(c.ciLow) + " to " + pts(c.ciHigh)],
      ["p-value (read once)", pFmt(c.pValue)],
      ["Always-valid p-value", pFmt(d.alwaysValidP)],
      ["Traffic split p-value", pFmt(d.srmP)]
    ]);
    $("tBayes").innerHTML = rowsHtml([
      ["Chance B is better", F.pct(b.probBBeatsA, 1)],
      ["Expected loss if you ship B", (100 * b.expectedLossChooseB).toFixed(3) + " pts"],
      ["Expected loss if you keep A", (100 * b.expectedLossChooseA).toFixed(3) + " pts"],
      ["Your loss tolerance", (100 * d.lossTol).toFixed(3) + " pts"],
      ["95% credible interval (B − A)", pts(b.diffCiLow) + " to " + pts(b.diffCiHigh)],
      ["Prior", $("prior").value === "flat" ? "Flat, Beta(1, 1)" : "Skeptical, 1,000 visitors each"]
    ]);
    var g = b.grid, stepN = Math.max(1, Math.floor(g.xs.length / 300)), pa = [], pb = [];
    for (var i = 0; i < g.xs.length; i += stepN) { pa.push([g.xs[i] * 100, g.pdfA[i]]); pb.push([g.xs[i] * 100, g.pdfB[i]]); }
    {
      Tool.lineChart($("postChart"), {
        series: [{ label: "A", color: "neutral", points: pa, area: true }, { label: "B", color: "accent", points: pb, area: true }],
        xTitle: "true conversion rate (%)", yTitle: "plausibility", yTicks: [], legend: true, height: 220,
        xFormat: function (x) { return x.toFixed(Math.abs(pa[pa.length - 1][0] - pa[0][0]) < 2 ? 2 : 1); }
      });
    }
  }
  function rowsHtml(rows) { return "<tbody>" + rows.map(function (r) { return "<tr><td>" + r[0] + '</td><td class="num">' + r[1] + "</td></tr>"; }).join("") + "</tbody>"; }
  document.querySelectorAll("details.more").forEach(function (det) { det.addEventListener("toggle", function () { if (det.open && last) renderDetails(); }); });

  function summaryText() {
    var L = last, d = L.d, v = L.v, c = d.classic;
    var lift = L.rateA > 0 ? (L.rateB - L.rateA) / L.rateA : NaN;
    return [
      "A/B test: " + L.title,
      L.body,
      "",
      "A: " + F.pct(L.rateA, 2) + " (" + F.int(v.xA) + " / " + F.int(v.nA) + ")   B: " + F.pct(L.rateB, 2) + " (" + F.int(v.xB) + " / " + F.int(v.nB) + ")",
      "Lift: " + rel(lift) + " relative, " + pts(c.diff) + " (95% CI " + pts(c.ciLow) + " to " + pts(c.ciHigh) + ")",
      "Chance B is better: " + F.pct(d.bayes.probBBeatsA, 1) + (d.peeked ? "   Always-valid p: " : "   p: ") + pFmt(d.evidenceP),
      "Checks: " + L.checks.map(function (x) { return x[2].toLowerCase() + " " + x[1].toLowerCase(); }).join(", "),
      "",
      "Open with these numbers: " + location.href
    ].join("\n");
  }

  /* ---------- plan ---------- */
  function runPlan() {
    var v = { pRate: num("pRate"), pMde: num("pMde"), pMdeUnit: $("pMdeUnit").value, pTraffic: num("pTraffic"),
      pVersions: Number($("pVersions").value), pPower: Number($("pPower").value), pAlpha: num("pAlpha") };
    var ok = true;
    function need(id, cond, msg) { fieldError(id, cond ? "" : msg); if (!cond) ok = false; }
    need("pRate", v.pRate > 0 && v.pRate < 100, "Between 0 and 100.");
    need("pMde", v.pMde > 0, "Above 0.");
    need("pTraffic", v.pTraffic > 0, "Above 0.");
    need("pAlpha", v.pAlpha > 0 && v.pAlpha < 50, "0.1 to 20.");
    var urlState = { mode: "plan" }; IDS_P.forEach(function (k) { urlState[k] = $(k).value; });
    Tool.writeParams(urlState);
    if (!ok) { $("pTitle").textContent = "Check the highlighted inputs"; $("pBody").textContent = ""; $("pKpis").innerHTML = ""; $("checksP").innerHTML = ""; return; }
    var p1 = v.pRate / 100, mdeAbs = v.pMdeUnit === "rel" ? p1 * v.pMde / 100 : v.pMde / 100;
    if (p1 + mdeAbs >= 1) { fieldError("pMde", "Lift takes the rate above 100%."); return; }
    var n = Decide.sampleSizePerArm(p1, mdeAbs, v.pAlpha / 100, v.pPower, v.pVersions);
    var total = n * v.pVersions, days = total / v.pTraffic, weeks = Math.max(1, Math.ceil(days / 7));
    var mdeWeeks = Decide.detectableLift(p1, Math.floor(weeks * 7 * v.pTraffic / v.pVersions), v.pAlpha / 100, v.pPower, v.pVersions);
    lastPlan = { v: v, n: n, total: total, days: days, weeks: weeks, mdeAbs: mdeAbs, p1: p1 };
    $("pTitle").textContent = F.int(n) + " visitors per version";
    $("pBody").textContent = "To see " + F.pct(p1, 2) + " move to " + F.pct(p1 + mdeAbs, 2) + ": " + F.int(total) + " visitors in total: about " + Math.ceil(days) + " day" + (Math.ceil(days) === 1 ? "" : "s") + " at " + F.int(v.pTraffic) + " a day. Run it for " + weeks + " full week" + (weeks === 1 ? "" : "s") + " (" + weeks * 7 + " days), and read the result once at the end." + (weeks * 7 > days * 1.15 ? " Running the full weeks also lets you detect a lift as small as " + (v.pMdeUnit === "rel" ? (100 * mdeWeeks / p1).toFixed(1) + "% relative." : (100 * mdeWeeks).toFixed(2) + " points.") : "");
    lastPlan.title = $("pTitle").textContent; lastPlan.body = $("pBody").textContent;
    $("pKpis").innerHTML = [
      [F.int(total), "visitors in total"],
      [Math.ceil(days) + " d", "days of traffic needed"],
      [weeks + " wk", "run length (whole weeks)"],
      [v.pVersions > 2 ? (v.pAlpha / (v.pVersions - 1)).toFixed(2) + "%" : v.pAlpha + "%", v.pVersions > 2 ? "significance per comparison" : "significance level"]
    ].map(function (it) { return '<div class="kpi"><span class="k-val">' + it[0] + '</span><span class="k-lbl">' + it[1] + "</span></div>"; }).join("");
    var cks = [];
    cks.push(["ok", "WEEKS", "Weekly cycles", "Rounded up to whole weeks so every weekday is equally represented."]);
    if (v.pVersions > 2) cks.push(["warn", "ADJUSTED", "Several versions", v.pVersions - 1 + " comparisons with the original, so each uses a significance level of " + (v.pAlpha / (v.pVersions - 1)).toFixed(2) + "% (Bonferroni). That is why each version needs more visitors."]);
    else cks.push(["ok", "OK", "Several versions", "One comparison, no correction needed."]);
    if (weeks > 8) cks.push(["warn", "LONG", "Run length", "Over 8 weeks: cookies expire, users switch devices and seasons change, which blurs the comparison. Consider testing for a larger lift or on a busier page."]);
    else cks.push(["ok", "OK", "Run length", "Short enough that cookie churn and seasonality should not blur the result."]);
    if (n * 2 * p1 < 200) cks.push(["warn", "LOW", "Expected conversions", "Under about 100 conversions per version: results will be fragile. Consider a higher-traffic page or a closer metric."]);
    $("checksP").innerHTML = cks.map(function (c) { return '<div class="check is-' + c[0] + '"><span class="badge">' + c[1] + '</span><div><span class="c-name">' + c[2] + '.</span> <span class="c-text">' + c[3] + "</span></div></div>"; }).join("");
    lastPlan.checks = cks;
    var pts2 = [], hl = null;
    for (var w = 1; w <= 8; w++) {
      var nn = Math.floor(w * 7 * v.pTraffic / v.pVersions);
      var mm = Decide.detectableLift(p1, nn, v.pAlpha / 100, v.pPower, v.pVersions);
      pts2.push([w, v.pMdeUnit === "rel" ? 100 * mm / p1 : 100 * mm]);
      if (w === weeks) hl = w - 1;
    }
    Tool.lineChart($("planChart"), {
      series: [{ points: pts2, color: "accent", markers: true, highlight: hl }],
      hLines: [{ y: v.pMde, labelLeft: true, label: "your target: " + v.pMde + (v.pMdeUnit === "rel" ? "%" : " pts"), color: "series2" }],
      xTitle: "test length (weeks)", yTitle: v.pMdeUnit === "rel" ? "detectable lift (% relative)" : "detectable lift (points)",
      xTicks: [1, 2, 3, 4, 5, 6, 7, 8], yMin: 0, height: 240,
      xFormat: function (x) { return String(x); }, yFormat: function (y) { return y.toFixed(y < 10 ? 1 : 0); }
    });
  }
  function planText() {
    var P = lastPlan;
    return ["A/B test plan: " + P.title, P.body, "", "Checks: " + P.checks.map(function (c) { return c[2].toLowerCase(); }).join(", "), "", "Open this plan: " + location.href].join("\n");
  }

  setMode(state.mode === "plan" ? "plan" : "analyze");
})();
