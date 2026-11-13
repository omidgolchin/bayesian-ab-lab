You are helping a product team read the result of an A/B test.

The metric is the {metric}. Version A is the current version and version B is the new one.

Results so far:
- Version A: {x_a} conversions out of {n_a} visitors ({rate_a_pct}% converted)
- Version B: {x_b} conversions out of {n_b} visitors ({rate_b_pct}% converted)

Context: {context}

Answer with a single JSON object and nothing else, in exactly this shape:
{{"decision": "ship_b" | "ship_a" | "keep_testing", "prob_b_better_percent": <number from 0 to 100>, "concerns": "<one short sentence, or empty string>"}}

- "decision": ship B now, ship A (keep the current version and drop B), or keep testing because the evidence is not strong enough yet.
- "prob_b_better_percent": your probability, as a percentage, that B's true conversion rate is higher than A's.
- "concerns": anything about how this test was run or how much data it has that should change how much the team trusts the result. Write an empty string if there is nothing.
