# Report for review — P14 bayesian-ab-lab

```text
PROJECT: P14 bayesian-ab-lab
STATUS IN ONE LINE: A Bayesian A/B test calculator and a peeking simulator, built on the Cookie Cats data, plus a check of whether an LLM reads A/B results correctly. — BUILT, all parts complete and verified locally.
CV CLUSTER: B (decisions).
DECISION NEEDED FROM OMID: none for the build. GitHub repo creation/push is pending Omid's repository-access selection (see §2).
DEFINITION CHECKLIST:
  [x] Research question: what does an A/B result really tell you, what goes wrong when you check results early, and can an LLM interpret a test correctly?
  [x] Data: Cookie Cats mobile-game A/B test (Kaggle; also a DataCamp project). License checked: listed as "Unknown" → download script, no redistribution.
  [x] Method: (1) calculator; (2) peeking simulator; (3) analysis of Cookie Cats both ways; (4) LLM check.
  [x] Key figure: false-positive rate vs number of peeks, classic test vs Bayesian decision rule (results/figures/peeking_fpr.png).
  [x] Limitations: conversion-type metrics only; one real dataset.
  [x] Done: calculator and simulator live on the page, Cookie Cats analysis and LLM check in results/summary.md.
BUDGET / LIMITS: $3 of model calls. Spent ≈ $0.39.
OPEN QUESTIONS: none.
```

## 1. What was built, and the result

A learner's lab for reading A/B tests two ways, in
`~/workspace/bayesian-ab-lab/`:

- Plan and freeze: [PLAN.md](PLAN.md), [FREEZE_MANIFEST.txt](FREEZE_MANIFEST.txt)
- Full computed write-up: [results/summary.md](results/summary.md);
  figures in [results/figures/](results/figures/)
- Playground: [docs/index.html](docs/index.html) (calculator with
  editable priors and presets, Cookie Cats tab, peeking tab with the
  power-calculation fix, Thompson-sampling tab, LLM-check tab);
  screenshots in [docs/screenshots/](docs/screenshots/)
- Decisions log: [DECISIONS.md](DECISIONS.md); spend: [SPEND.md](SPEND.md)

**Result.** Three findings, all computed from the frozen plan:

1. **Peeking hurts the Bayesian rule more than the classic one at
   these settings.** Over 5,000 simulated pairs of identical arms
   checked every 250 visitors per arm, the classic stop-at-p<0.05
   rule's false-positive rate climbs 4.5% → 13.2% → 18.1% → 29.1%
   (1 / 5 / 10 / 40 looks), tracking Armitage et al.'s 1969
   tabulation. The Bayesian stop-at-expected-loss (< 0.05 points)
   rule climbs 8.4% → 32.4% → 49.0% → **85.0%**. A fixed loss
   threshold is an absolute yardstick while uncertainty shrinks with
   n, so late looks cross it on noise alone. The fix stays boring:
   fix the size in advance (3,839/arm for +2 points at 80% power),
   look once.
2. **Cookie Cats:** moving the gate from level 30 to 40 hurt
   retention on both metrics and both reads agree — 1-day −0.59
   points (classic p = 0.074; P(gate_40 better) = 3.7%) and 7-day
   −0.82 points (p = 0.0016; P = 0.08%), with the bootstrap interval
   matching both parametric intervals.
3. **The LLM check:** Inkling-2-Small's code mode was the strongest
   combination (decision accuracy 0.96 over scored items, mean
   probability error 1.2 points, 7/9 planted problems flagged);
   gpt-oss-120b's direct mode was well calibrated (1.2 points) with
   weaker decisions (0.73). The failures were specific: gpt-oss's
   code twice computed the *complementary* probability and once fell
   into the needle-posterior quadrature trap at n = 100,000 (the
   same trap this repo's own calculator refactor had to avoid); all
   six of Inkling's direct format failures were empty replies on
   problem items, its reasoning running to the 4,000-token limit.

Also worth knowing: of eleven models piloted for the check, only two
could answer all five pilot items in the required format in both
modes — the pilot table in PLAN.md is a result in its own right.

## 2. Deviations from the spec, and every DECISIONS.md entry

Deviations:

- **GitHub repo not created, nothing pushed.** Per instruction for
  this pass (repository-access selection still pending on Omid's
  side). The local git history is complete (git user "Omid Golchin"
  <omidgolchin92@gmail.com>, small meaningful commits). Creating the
  private repo `bayesian-ab-lab` under `omidgolchin`, setting the
  description/topics, and pushing are recorded as pending.
- **Token budget for the LLM check raised 1,200 → 4,000 before the
  freeze** (DECISIONS #13). At 1,200 tokens nearly every cheap
  serverless model spent the whole budget on hidden reasoning and
  returned empty answers; the pilot was re-run in full at the new
  budget, and the change is documented in PLAN.md. This changes a
  run parameter, not a scoring rule or any item.
- **Three post-freeze corrections, all logged and re-frozen**
  (DECISIONS #15–#17): a direction bug in the grid difference-CDF
  (caught by the spec's own tests; LLM ground truth verified
  unaffected), item 24's counts corrected before the run reached it,
  and a CSV-writer crash fix in the analysis tooling. No method,
  item, or scoring rule changed after the freeze.
- **Dependency pins bumped** (scipy 1.11.4 → 1.12.0, matplotlib
  3.6.3 → 3.8.4) because the original pins have no CPython 3.12
  wheels (DECISIONS #2).

DECISIONS.md entries (each with its reason in the file):

1. Cookie Cats license "Unknown" → download script only; data via
   the author's GitHub mirror after shape verification.
2. Dependency pins bumped for Python 3.12 wheels.
3. Exact formulas below 2,000 total visitors, fitted grid above,
   bound together by tests.
4. Peeked items 24/26 counts set so the final p < 0.05, matching
   their "stopped at first significance" stories.
5. Item 20 is a genuine ship_b under the frozen rule (large effect,
   tiny downside) — kept deliberately.
6. Code-mode decisions derived from the computed probability only;
   peeked items not decision-scored in code mode.
7. Problem-flagging scored by keyword match — generous and
   mechanical, reported as such.
8. Model pool set by probing, not preference; non-serverless and
   403 models excluded by probe results.
9. NO_PROXY sanitisation in the API client builder (environment
   quirk that killed the client constructor).
10. Thompson null-case semantics: "confident and right" = ended
    uncommitted.
11. The code sandbox is a convenience, not a security boundary.
12. Plain-language sentences rule-written in both implementations.
13. Token budget 1,200 → 4,000 after pilot round 1 (see above).
14. Model selection landed on gpt-oss-120b + Inkling-2-Small (the
    only two of eleven piloted models to meet the rule).
15. Post-freeze grid difference-CDF direction fix (see above).
16. Item 24 counts corrected mid-run, before it was reached.
17. Post-freeze scores-CSV writer fix (see above).

## 3. Spend

**≈ $0.39 of the $3 cap** (311 API calls). By step: probes ≈ $0.005;
pilots $0.225 across three batches and two budget rounds; main run
$0.158 (gpt-oss-120b $0.031, Inkling-2-Small $0.127). Full table in
[SPEND.md](SPEND.md), computed from returned usage at catalog prices.

## 4. Tests and reproducibility

- `pytest`: **15/15 pass**, including the spec's named checks —
  posterior quantities and P(B > A) vs a 600,000-draw Monte Carlo on
  three cases; one-look false-positive rate 5% ± Monte Carlo error;
  JavaScript and Python calculators agree on fixed cases — plus
  grid-vs-exact agreement and the Armitage-neighbourhood peeking
  behaviour.
- Reproduce: fresh clone → `make setup && make data` (the download
  script's mirror fallback fired and verified the file) → copy the
  saved run log into `outputs/` → `python -m src.bayesab.analyze`.
  **Verified clean from a fresh clone** (on the home filesystem; a
  first attempt inside /tmp failed for an environment reason — the
  512 MB tmpfs filled during the venv install — and was redone):
  15/15 tests pass, and the regenerated `results/summary.md` is
  identical, both figures are byte-identical, and all 120 score rows
  match with a worst numeric difference of 0.013 points (sandboxed
  quadrature wobble on one code-mode row; no text differences).
- CI: `.github/workflows/ci.yml` is written (pytest + smoke test, no
  API calls) but has not run on GitHub, because the repo does not
  exist yet.

## 5. Known issues and things I am unsure about

- `analyze` takes ~7–10 minutes, dominated by the peeking
  simulation's grid evaluation (5,000 tests × 40 looks). It is a
  one-command wait, not a failure, but a faster implementation
  (fewer grid points, or the series form for the losses) would be
  the first improvement to make.
- In the sandbox screenshots the Chart.js CDN is unreachable, so the
  committed screenshots show the hand-drawn fallback charts. The
  fallback is fully functional; in a normal browser the pinned
  Chart.js 4.4.1 renders instead. Both paths were checked against
  the same data.
- The LLM check is one run per item per model at temperature 0.7.
  Inkling's direct format failures (6/30, all truncated reasoning)
  might partly be luck of the draw; the pattern (all six on problem
  items) is reported as observed, not as a stable rate.
- Keyword-based flag scoring can credit a stock phrase and miss a
  genuine concern phrased unusually. Per-item raw replies are in
  `outputs/llmcheck_runs.jsonl` (git-ignored, available locally) for
  anyone who wants to re-judge them by hand.
- One code-mode row (gpt-oss, item 18) is scored from a sandboxed
  `scipy.quad` evaluation of a needle-shaped integrand; the same
  script can return slightly different values on different machines.
  The reproduce run's worst per-cell score difference was 0.013
  points, on exactly this kind of row.

## 6. Playground screenshots

- Calculator, desktop (1280 px):
  [docs/screenshots/playground-desktop.png](docs/screenshots/playground-desktop.png)
- Calculator, phone (375 px):
  [docs/screenshots/playground-phone.png](docs/screenshots/playground-phone.png)
- Peeking tab, desktop:
  [docs/screenshots/peeking-desktop.png](docs/screenshots/peeking-desktop.png)

## 7. Draft LinkedIn post (do not post — for Omid's review)

> I built a small lab to check two ways of reading an A/B test
> against each other — the classic significance test and the
> Bayesian expected-loss read — and then pointed it at the habit
> that breaks both: peeking. Over 5,000 simulated tests where A and
> B are identical, checking every 250 visitors, the classic rule's
> false-positive rate climbs from 4.5% to 29% by 40 looks. The
> Bayesian rule, stopping when the expected loss looks tiny, climbs
> to 85%. A fixed loss threshold does not protect you when the
> uncertainty keeps shrinking. Fix the sample size first, then look
> once. I also checked whether two LLMs can read A/B results
> correctly, judging directly versus writing the code — the code
> mode won, and its failures were the interesting part. Link in the
> comments. #ABTesting #Bayesian #LLMEvaluation
