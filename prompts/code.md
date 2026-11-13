You are helping a product team read the result of an A/B test by computing the answer in Python.

The metric is the {metric}. Version A is the current version and version B is the new one.

Results so far:
- Version A: {x_a} conversions out of {n_a} visitors
- Version B: {x_b} conversions out of {n_b} visitors

Context: {context}

Write a Python script that computes, from these counts:
1. the probability that B's true conversion rate is higher than A's, using independent Beta(1, 1) priors on the two rates;
2. the two-sided p-value of the pooled two-proportion z-test.

The script must print exactly one line containing a JSON object of the form {{"prob_b_better": <number between 0 and 1>, "p_value": <number between 0 and 1>}} and nothing else on stdout. You may use the standard library plus numpy and scipy. Put the script in a single ```python code block. Outside the code block, you may add one short sentence of concerns about how this test was run or how much data it has, prefixed with "Concern:" — or write nothing outside the block.
