# Decisions log

Choices made while building, with the reason for each. Per the program
rules: where the spec left a choice open, the more conservative option
was taken and logged here; nothing waited on a human checkpoint.

1. **Cookie Cats data is not redistributed.** The Kaggle page lists the
   license as "Unknown", so the repo ships `scripts/download_data.py`
   only, and `data/*.csv` is git-ignored. The script tries the Kaggle
   API first and falls back to the dataset author's own GitHub mirror;
   it verifies the file (90,189 rows; gate_30 44,700 / gate_40 45,489)
   before accepting it. In this build environment the Kaggle API was
   not usable, so the mirror copy was used; its group rates match the
   published values to six decimals (retention_1 0.448188 / 0.442283;
   retention_7 0.190201 / 0.182000).
2. **Dependency pins bumped for Python 3.12 wheels.** The first-choice
   pins (scipy 1.11.4, matplotlib 3.6.3) predate CPython 3.12 and have
   no wheels for it, so pip tried to build matplotlib from source and
   failed. Pins are now scipy 1.12.0 / matplotlib 3.8.4 (first versions
   with cp312 wheels in their lines). Nothing in the project depends on
   behaviour that changed between those versions. (The sandbox's /tmp
   is also a small tmpfs; pip is run with a project-local TMPDIR.)
3. **Exact formulas below 2,000 total visitors, grid above.** The exact
   quadrature/bisection path is the reference definition but crawls on
   needle-shaped posteriors at large n. Above 2,000 total visitors a
   fitted-grid computation is used; the tests check it against the
   exact formulas at 2,000/arm and against Monte Carlo at
   Cookie-Cats size. The JavaScript calculator uses the same grid idea.
4. **Peeked items 24 and 26 had their counts adjusted** (B conversions
   270→272 and 64→68) so the final two-sided p-value is below 0.05,
   matching their story ("stopped the first day the result showed as
   significant"). Without the adjustment the story and the numbers
   contradicted each other.
5. **Item 20 is a genuine ship_b.** Its ground truth under the frozen
   rule is ship_b despite the small sample: the effect is large (2.5%
   vs 8.2%) and the expected loss of shipping is tiny because both
   rates are low. It is kept deliberately — it separates "notices the
   small sample" (still scored, via the concerns field) from "refuses
   every small sample" (which the rule does not do).
6. **Code-mode decisions are derived from the computed probability
   only** (ship B ≥ 0.95, ship A ≤ 0.05), and peeked items are not
   decision-scored in code mode: a computed probability cannot express
   "this read cannot be trusted", so those items are scored on
   probability accuracy and problem-flagging instead. Fixed in PLAN.md
   before the run.
7. **Problem-flagging is scored by keyword match** on the model's own
   stated concerns (frozen list in `items.py`). It is generous and
   mechanical — a model can earn the flag with a stock phrase — and the
   summary says so rather than dressing it up as understanding.
8. **Model pool determined by probing, not preference.** Every cheap
   catalog chat model was probed with one short call first. Several
   (trinity-mini, Nemotron-Nano-9B, gpt-oss-20b, Mistral-Small-24B,
   Llama-3.2-3B, Llama-3.1-8B-Turbo, Qwen2-1.5B, Ministral-3-14B)
   returned "non-serverless" errors on this account, and
   Qwen3.8-Flash returned 403 (third-party data sharing not enabled).
   The pilot pool is the six cheapest models that answered:
   Tev1-4B-experimental, GLM-5.3-Flash, MiniMax-M3.1-Flash,
   gpt-oss-120b, Qwen3.5-9B, DeepSeek-V4.1-Flash.
9. **NO_PROXY sanitisation in `run.get_client`.** This environment
   exports a NO_PROXY containing "[::1]", which the pinned httpx
   cannot parse, killing the OpenAI client constructor. The client
   builder drops bracketed entries in-process; routing is unaffected
   (api.together.xyz is not in the no-proxy list).
10. **Thompson "confident and right" in the no-difference scenario**
    means *ended uncommitted*: with identical arms, any confident
    directional read is wrong, so the null table reports confident-and-
    wrong directly and treats the uncommitted share as the honest
    outcome. The playground labels it that way.
11. **The sandbox is a convenience, not a boundary.** Model-written
    code runs in a subprocess with a scrubbed environment, a 60-second
    timeout, a throwaway directory, and `unshare -n` network isolation
    where the binary exists. That is proportionate for generated
    statistics code that a human also reads; it is not claimed to stop
    a determined adversary.
12. **Sentences are rule-written in both implementations.** The Python
    and JavaScript sentence generators use the same thresholds and
    near-identical templates, so the playground and the written summary
    tell the same story in the same words.
13. **Token budget raised 1,200 → 4,000 after pilot round 1.** Most
    cheap serverless models on Together are reasoning-style: at 1,200
    tokens they spent the whole budget on hidden reasoning and
    returned empty or truncated answers (only gpt-oss-120b finished
    10/10). 4,000 tokens is generous for a one-line JSON answer, is
    applied uniformly to every model, and still leaves the projected
    main-run cost under $0.25. The change was made and logged before
    the freeze, and the pilot was re-run in full at the new budget
    (round 1 kept as `outputs/pilot_runs_v1.jsonl`). Models are scored
    on their final answer text only, never on a reasoning channel.
14. **Model selection landed on gpt-oss-120b + Inkling-2-Small.**
    Eleven models were piloted across three batches (every serverless
    chat model cheaper than the winners was tried; several catalog
    models are not serverless on this account at all). Only these two
    answered all 5 pilot items in the required format in both modes.
    The near-misses are informative and are reported in PLAN.md:
    Glimmer 9/10, DeepSeek 8/10. Kimi-K3 ($3/$15 per 1M) was probed
    but not piloted: at 20x the winners' price it could not be among
    "the cheapest that qualify" unless everything cheaper failed,
    which it did not.

15. **Post-freeze fix: the grid difference-CDF ran in the survival
    direction.** The first full test run caught `_grid_pack` returning
    the *lower edge of the grid* as the credible interval's low end:
    it integrated F_A(p_B − d) (the survival function of the
    difference) instead of F_B(p_A + d). The JavaScript version had
    the same bug and was fixed first; the Python one was caught by
    the JS-agreement and Monte Carlo tests. Fixed, all 15 tests pass,
    and the manifest was re-issued. The LLM check was unaffected: its
    ground truth uses P(B beats A) and the expected losses, which were
    correct in both versions (verified item by item after the fix).
16. **Item 24 counts corrected mid-run (272 → 278 B conversions).**
    The first adjustment (decision 4) undershot: the final two-sided
    p was 0.080, still contradicting the item's "stopped at first
    significance" story. The correction was made before the main run
    reached item 24 and before any analysis; the run was stopped and
    resumed (the runner skips completed run IDs, and the 42 rows
    already written are for other items and unaffected). Final
    item 24: p = 0.043, P(B beats A) = 0.978, ground truth
    keep_testing (peeked override).

17. **Post-freeze tooling fix: scores CSV writer.** The first full
    `analyze` run crashed at the CSV step because code-mode score rows
    carry two fields direct-mode rows do not (`pvalue_error`,
    `code_ran`), and the writer took its fieldnames from the first
    row. The writer now uses the union of keys. No method, input, or
    number changed; the manifest was re-issued. (The simulations are
    seeded, so the re-run reproduces identical values.)

