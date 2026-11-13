# Spend

Cap for this project: **$3.00** (program budget). Costs are computed
from the token usage returned with each response, at the catalog prices
shown (per 1M tokens, as listed by the Together models API on
2026-11-12). Calls that errored before returning usage are counted as
$0 and noted.

| step | models | calls | tokens (in/out) | cost |
|---|---|---|---|---|
| serverless probes | 21 models, one short call each | 21 | ~1,400 / ~600 | ≈ $0.005 |
| pilot round 1 (1,200-token budget) | 6 models × 5 items × 2 modes | 60 | 19,566 / 53,678 | $0.0367 |
| pilot round 2 (4,000-token budget) | same 6 models | 60 | 19,568 / 145,680 | $0.0900 |
| pilot batch 2 | qwen-2-1.5b, Nemotron-3.5-Super-VL, Ripple-65B | 30 | 8,695 / 63,856 | $0.0356 |
| pilot batch 3 | Muse-Glimmer-30B, Inkling-2-Small | 20 | 6,333 / 46,972 | $0.0626 |
| main run (30 items × 2 modes × 2 models) | gpt-oss-120b, Inkling-2-Small | 120 | 38,986 / 167,646 | $0.1579 |
| **total** | | **311** | | **≈ $0.39** |

Main run by model: gpt-oss-120b $0.0306; Inkling-2-Small $0.1273
(Inkling is the more expensive model per token and writes longer
answers). Pilot detail by model is in PLAN.md's pilot table.
The project finished at about 13% of its cap; the binding constraint
throughout was not money but how many cheap serverless models could
follow the answer format at all (see DECISIONS.md #13, #14).

Prices used: Tev1-4B-experimental $0.042 in / $0.00 out;
GLM-5.3-Flash $0.15 / $0.50; MiniMax-M3.1-Flash $0.15 / $0.60;
gpt-oss-120b $0.15 / $0.60; Qwen3.5-9B $0.17 / $0.25;
DeepSeek-V4.1-Flash $0.30 / $1.20; qwen-2-1.5b-instruct $0.10 / $0.10;
Nemotron-3.5-Super-VL $0.15 / $0.50; Ripple-65B-Preview $0.20 / $0.60;
Muse-Glimmer-30B $0.35 / $1.50; Inkling-2-Small $0.30 / $1.00.
