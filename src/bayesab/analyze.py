"""Regenerate everything in results/ and docs/data/ from the frozen inputs.

One command:  python -m src.bayesab.analyze

Reads the Cookie Cats CSV (data/, see scripts/download_data.py), the
simulation settings (config.yaml), and the LLM-check run log
(outputs/llmcheck_runs.jsonl). Writes:

* results/summary.md      -- the headline write-up, numbers in prose
* results/llmcheck_scores.csv
* docs/data/cookiecats.json, peeking.json, thompson.json, llmcheck.json
  -- the JSON the playground charts from
* results/figures/*.png   -- static figures for the README
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
DOCDATA = ROOT / "docs" / "data"
FIGURES = RESULTS / "figures"


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1))


def _fmt(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}"


def main() -> None:
    from .cookiecats import analyze_cookie_cats
    from .items import load_items
    from .simulate import required_n_per_arm, simulate_peeking, simulate_thompson

    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    sim_cfg = config["simulation"]

    RESULTS.mkdir(parents=True, exist_ok=True)
    DOCDATA.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    # ---- Cookie Cats ------------------------------------------------------
    cc = analyze_cookie_cats()
    _write_json(DOCDATA / "cookiecats.json", cc)

    # ---- peeking + thompson simulations -----------------------------------
    peeking = simulate_peeking(
        n_tests=sim_cfg["n_tests"], base_rate=sim_cfg["base_rate"],
        peek_every=sim_cfg["peek_every"], max_peeks=sim_cfg["max_peeks"],
        seed=sim_cfg["seed"],
    )
    peeking["armitage_1969"] = {  # JRSS A 132(2), Table (equally spaced looks)
        "looks": [1, 2, 5, 10, 20], "fpr": [0.050, 0.083, 0.142, 0.193, 0.246],
    }
    peeking["fixed_design"] = {
        "mde": 0.02, "power": 0.80,
        "n_per_arm": required_n_per_arm(sim_cfg["base_rate"], 0.02),
    }
    _write_json(DOCDATA / "peeking.json", peeking)

    th_cfg = sim_cfg["thompson"]
    thompson = simulate_thompson(
        n_sims=th_cfg["n_sims"], horizon=th_cfg["horizon"],
        p_a=th_cfg["p_a"], p_b=th_cfg["p_b"], seed=th_cfg["seed"],
    )
    null_cfg = dict(th_cfg)
    thompson_null = simulate_thompson(
        n_sims=th_cfg["n_sims"], horizon=th_cfg["horizon"],
        p_a=th_cfg["p_a"], p_b=th_cfg["p_a"], seed=th_cfg["seed"] + 1,
    )
    _write_json(DOCDATA / "thompson.json",
                {"effect": thompson, "no_effect": thompson_null})

    # ---- LLM check scores ---------------------------------------------------
    from .score import score_row

    items = {it["id"]: it for it in load_items()}
    runs_path = ROOT / "outputs" / "llmcheck_runs.jsonl"
    scores: list[dict] = []
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("dry_run"):
                continue
            scores.append(score_row(row, items[row["item_id"]]))
    if scores:
        # Direct and code rows carry slightly different fields; write the
        # union, in first-appearance order.
        fieldnames = list(dict.fromkeys(k for s in scores for k in s))
        with (RESULTS / "llmcheck_scores.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(scores)
    llm_summary = _llm_summary(scores, items)
    _write_json(DOCDATA / "llmcheck.json",
                {"summary": llm_summary, "scores": scores,
                 "items": [items[k] for k in sorted(items)]})

    # ---- figures ------------------------------------------------------------
    _figures(cc, peeking, thompson, thompson_null)

    # ---- summary.md ---------------------------------------------------------
    (RESULTS / "summary.md").write_text(
        _summary_md(cc, peeking, thompson, thompson_null, llm_summary, items,
                    scores)
    )
    print("wrote results/summary.md, results/llmcheck_scores.csv, "
          "docs/data/*.json, results/figures/*.png")


def _llm_summary(scores: list[dict], items: dict) -> dict:
    summary: dict = {}
    for s in scores:
        key = (s["model"], s["mode"])
        agg = summary.setdefault(key, {
            "model": s["model"], "mode": s["mode"], "n": 0, "format_ok": 0,
            "decisions_scored": 0, "decisions_correct": 0,
            "prob_errors": [], "flags_scored": 0, "flags_hit": 0,
        })
        agg["n"] += 1
        agg["format_ok"] += bool(s["format_ok"])
        if s["decision_correct"] is not None:
            agg["decisions_scored"] += 1
            agg["decisions_correct"] += bool(s["decision_correct"])
        if s["prob_error_pp"] is not None:
            agg["prob_errors"].append(s["prob_error_pp"])
        item = items[s["item_id"]]
        if item["has_problem"] and s["flagged_problem"] is not None:
            agg["flags_scored"] += 1
            agg["flags_hit"] += bool(s["flagged_problem"])
    out = []
    for agg in summary.values():
        errs = agg.pop("prob_errors")
        agg["mean_prob_error_pp"] = (
            sum(errs) / len(errs) if errs else None)
        agg["decision_accuracy"] = (
            agg["decisions_correct"] / agg["decisions_scored"]
            if agg["decisions_scored"] else None)
        agg["flag_rate"] = (
            agg["flags_hit"] / agg["flags_scored"] if agg["flags_scored"]
            else None)
        out.append(agg)
    return out


def _figures(cc, peeking, thompson, thompson_null) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    r1 = cc["metrics"]["retention_1"]
    r7 = cc["metrics"]["retention_7"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for ax, r, title in ((axes[0], r1, "1-day retention"),
                         (axes[1], r7, "7-day retention")):
        labels = ["classic CI", "Bayesian CrI", "bootstrap CI"]
        cis = [r["classic_ci"], r["bayes_diff_ci"], r["bootstrap_ci"]]
        for i, (lab, (lo, hi)) in enumerate(zip(labels, cis)):
            ax.plot([lo * 100, hi * 100], [i, i], "o-", label=lab)
        ax.axvline(0, color="grey", lw=0.8)
        ax.set_yticks(range(3), labels)
        ax.set_xlabel("gate_40 minus gate_30 (points)")
        ax.set_title(title)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "cookie_cats_intervals.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(peeking["peeks"], [100 * v for v in peeking["classic_fpr"]],
            label="classic test, stop at p < 0.05")
    ax.plot(peeking["peeks"], [100 * v for v in peeking["bayes_fpr"]],
            label="Bayesian rule, stop at expected loss < 0.05 pts")
    ax.plot(peeking["armitage_1969"]["looks"],
            [100 * v for v in peeking["armitage_1969"]["fpr"]], "x--",
            label="Armitage et al. (1969), normal case")
    ax.axhline(5, color="grey", lw=0.8)
    ax.set_xlabel("number of looks at the data")
    ax.set_ylabel("false-positive rate (%)")
    ax.set_title("Peeking at identical A/B tests (true difference: zero)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "peeking_fpr.png", dpi=150)
    plt.close(fig)


def _summary_md(cc, peeking, thompson, thompson_null, llm_summary, items,
                scores) -> str:
    r1 = cc["metrics"]["retention_1"]
    r7 = cc["metrics"]["retention_7"]
    lines = [
        "# Results summary",
        "",
        "Every number below is computed by `python -m src.bayesab.analyze` "
        "from the frozen inputs (PLAN.md / FREEZE_MANIFEST.txt).",
        "",
        "## Cookie Cats: gate_30 vs gate_40",
        "",
        f"44,700 players got the gate at level 30 and 45,489 at level 40.",
        "",
        f"- **1-day retention:** gate_30 {_fmt(r1['rate_a'])}% vs gate_40 "
        f"{_fmt(r1['rate_b'])}% — difference {_fmt(r1['diff'])} points. "
        f"Classic: 95% CI {_fmt(r1['classic_ci'][0])} to "
        f"{_fmt(r1['classic_ci'][1])}, p = {r1['p_value']:.3f}. Bayesian: "
        f"P(gate_40 beats gate_30) = {r1['prob_b_beats_a']:.3f}; expected "
        f"loss of moving the gate to 40 is "
        f"{_fmt(r1['expected_loss_choose_b'], 3)} points. Bootstrap CI "
        f"{_fmt(r1['bootstrap_ci'][0])} to {_fmt(r1['bootstrap_ci'][1])} "
        f"agrees with both.",
        f"- **7-day retention:** gate_30 {_fmt(r7['rate_a'])}% vs gate_40 "
        f"{_fmt(r7['rate_b'])}% — difference {_fmt(r7['diff'])} points. "
        f"Classic: 95% CI {_fmt(r7['classic_ci'][0])} to "
        f"{_fmt(r7['classic_ci'][1])}, p = {r7['p_value']:.4f}. Bayesian: "
        f"P(gate_40 beats gate_30) = {r7['prob_b_beats_a']:.4f}. Both "
        f"reads say the same thing: moving the gate to level 40 made "
        f"retention worse, more clearly at 7 days than at 1.",
        "",
        "## Peeking",
        "",
        f"Simulated {peeking['settings']['n_tests']} pairs of identical "
        f"arms (true rate {_fmt(peeking['settings']['base_rate'], 0)}% "
        f"each), checked every {peeking['settings']['peek_every']} "
        f"visitors per arm, up to {peeking['settings']['max_peeks']} "
        f"looks:",
        "",
        f"- classic stop-at-p<0.05 rule: false-positive rate "
        f"{_fmt(peeking['classic_fpr'][0], 1)}% after 1 look, "
        f"{_fmt(peeking['classic_fpr'][4], 1)}% after 5, "
        f"{_fmt(peeking['classic_fpr'][9], 1)}% after 10, "
        f"{_fmt(peeking['classic_fpr'][-1], 1)}% after "
        f"{peeking['settings']['max_peeks']}.",
        f"- Bayesian stop-at-low-expected-loss rule: "
        f"{_fmt(peeking['bayes_fpr'][0], 1)}% after 1 look, "
        f"{_fmt(peeking['bayes_fpr'][4], 1)}% after 5, "
        f"{_fmt(peeking['bayes_fpr'][9], 1)}% after 10, "
        f"{_fmt(peeking['bayes_fpr'][-1], 1)}% after "
        f"{peeking['settings']['max_peeks']}. The Bayesian rule is **not** "
        f"immune to optional stopping: its rate climbs too. What changes "
        f"is the currency — the rule stops when the *cost of being wrong* "
        f"is small, not when a p-value crosses a line — but with a fixed "
        f"loss threshold and unlimited looks, it still manufactures "
        f"confident wrong answers more often than the threshold suggests.",
        f"- The honest fix costs nothing exotic: fix the size in advance. "
        f"Detecting +2 points on a {_fmt(peeking['settings']['base_rate'], 0)}% "
        f"base rate at 80% power needs "
        f"{peeking['fixed_design']['n_per_arm']:,} visitors per arm, one "
        f"look, and the false-positive rate is the advertised 5%.",
        "",
        "## Adaptive allocation (Thompson sampling vs 50/50)",
        "",
        f"With true rates 10% vs 12% over "
        f"{thompson['settings']['horizon']} visitors: fixed 50/50 averaged "
        f"{thompson['fixed']['mean_conversions']:.0f} conversions "
        f"(regret {thompson['fixed']['regret_vs_oracle']:.0f} vs the "
        f"oracle); Thompson sampling averaged "
        f"{thompson['thompson']['mean_conversions']:.0f} (regret "
        f"{thompson['thompson']['regret_vs_oracle']:.0f}). The catch: "
        f"Thompson ended with a confident-and-right final read in "
        f"{_fmt(thompson['thompson']['confident_and_right'], 1)}% of runs "
        f"vs {_fmt(thompson['fixed']['confident_and_right'], 1)}% for "
        f"50/50, because it starves the losing arm of data. With no true "
        f"difference, a confident-and-wrong read appeared in "
        f"{_fmt(thompson_null['thompson']['confident_and_wrong'], 1)}% of "
        f"Thompson runs vs "
        f"{_fmt(thompson_null['fixed']['confident_and_wrong'], 1)}% of "
        f"50/50 runs. More conversions during the test, weaker evidence "
        f"after it — that is the trade, stated plainly.",
        "",
        "## The LLM check",
        "",
    ]
    if llm_summary:
        lines.append("| model | mode | format ok | decision accuracy | "
                     "mean probability error (pts) | problems flagged |")
        lines.append("|---|---|---|---|---|---|")
        for agg in sorted(llm_summary, key=lambda a: (a["model"], a["mode"])):
            lines.append(
                f"| {agg['model']} | {agg['mode']} | "
                f"{agg['format_ok']}/{agg['n']} | "
                f"{agg['decision_accuracy']:.2f} "
                f"({agg['decisions_correct']}/{agg['decisions_scored']} "
                f"scored) | {agg['mean_prob_error_pp']:.1f} | "
                f"{agg['flags_hit']}/{agg['flags_scored']} |"
            )
        lines += [
            "",
            "Ground truth is this repo's calculator under the decision "
            "rule frozen in PLAN.md. For peeked items the correct decision "
            "is always 'keep testing', and code mode is not scored on the "
            "decision there (a computed probability cannot express 'this "
            "read cannot be trusted'). Flagging is scored by keyword match "
            "on the model's own stated concerns — a generous, mechanical "
            "check, reported as such.",
        ]
    else:
        lines.append("No LLM-check runs recorded yet.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
