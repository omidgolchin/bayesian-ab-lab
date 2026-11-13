# Results summary

Every number below is computed by `python -m src.bayesab.analyze` from the frozen inputs (PLAN.md / FREEZE_MANIFEST.txt).

## Cookie Cats: gate_30 vs gate_40

44,700 players got the gate at level 30 and 45,489 at level 40.

- **1-day retention:** gate_30 44.82% vs gate_40 44.23% — difference -0.59 points. Classic: 95% CI -1.24 to 0.06, p = 0.074. Bayesian: P(gate_40 beats gate_30) = 0.037; expected loss of moving the gate to 40 is 0.595 points. Bootstrap CI -1.24 to 0.05 agrees with both.
- **7-day retention:** gate_30 19.02% vs gate_40 18.20% — difference -0.82 points. Classic: 95% CI -1.33 to -0.31, p = 0.0016. Bayesian: P(gate_40 beats gate_30) = 0.0008. Both reads say the same thing: moving the gate to level 40 made retention worse, more clearly at 7 days than at 1.

## Peeking

Simulated 5000 pairs of identical arms (true rate 10% each), checked every 250 visitors per arm, up to 40 looks:

- classic stop-at-p<0.05 rule: false-positive rate 4.5% after 1 look, 13.2% after 5, 18.1% after 10, 29.1% after 40.
- Bayesian stop-at-low-expected-loss rule: 8.4% after 1 look, 32.4% after 5, 49.0% after 10, 85.0% after 40. The Bayesian rule is **not** immune to optional stopping: its rate climbs too. What changes is the currency — the rule stops when the *cost of being wrong* is small, not when a p-value crosses a line — but with a fixed loss threshold and unlimited looks, it still manufactures confident wrong answers more often than the threshold suggests.
- The honest fix costs nothing exotic: fix the size in advance. Detecting +2 points on a 10% base rate at 80% power needs 3,839 visitors per arm, one look, and the false-positive rate is the advertised 5%.

## Adaptive allocation (Thompson sampling vs 50/50)

With true rates 10% vs 12% over 4000 visitors: fixed 50/50 averaged 440 conversions (regret 40 vs the oracle); Thompson sampling averaged 464 (regret 16). The catch: Thompson ended with a confident-and-right final read in 52.5% of runs vs 65.2% for 50/50, because it starves the losing arm of data. With no true difference, a confident-and-wrong read appeared in 19.4% of Thompson runs vs 11.1% of 50/50 runs. More conversions during the test, weaker evidence after it — that is the trade, stated plainly.

## The LLM check

| model | mode | format ok | decision accuracy | mean probability error (pts) | problems flagged |
|---|---|---|---|---|---|
| openai/gpt-oss-120b | code | 30/30 | 0.85 (22/26 scored) | 13.8 | 4/9 |
| openai/gpt-oss-120b | direct | 30/30 | 0.73 (22/30 scored) | 1.2 | 5/9 |
| thinkingmachines/Inkling-2-Small | code | 29/30 | 0.96 (24/25 scored) | 1.2 | 7/9 |
| thinkingmachines/Inkling-2-Small | direct | 24/30 | 0.62 (15/24 scored) | 0.1 | 2/3 |

Ground truth is this repo's calculator under the decision rule frozen in PLAN.md. For peeked items the correct decision is always 'keep testing', and code mode is not scored on the decision there (a computed probability cannot express 'this read cannot be trusted'). Flagging is scored by keyword match on the model's own stated concerns — a generous, mechanical check, reported as such.
