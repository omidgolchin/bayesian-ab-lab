# Data sources

## Cookie Cats A/B test (the one real dataset)

- **What:** 90,189 players of the mobile game Cookie Cats (Tactile
  Entertainment), randomly assigned to a first gate at level 30
  (`gate_30`, n = 44,700) or level 40 (`gate_40`, n = 45,489), with
  1-day and 7-day retention recorded for each player.
- **Source:** "Mobile Games: A/B Testing" by Yufeng Sui on Kaggle —
  https://www.kaggle.com/datasets/yufengsui/mobile-games-ab-testing —
  which hosts the data from the DataCamp project "Mobile Games A/B
  Testing with Cookie Cats" (https://www.datacamp.com/projects/184).
- **License:** the Kaggle page lists the license as **"Unknown"**, so
  this repository does **not** redistribute the CSV. `data/` is
  git-ignored; get the file with `scripts/download_data.py` (Kaggle API
  route, with a fallback to the dataset author's own GitHub mirror,
  https://github.com/yfsui/Mobile-Games-AB-Testing-Project). The script
  verifies the file against the known shape (90,189 rows; group counts
  44,700 / 45,489) before accepting it. Only derived results (rates,
  differences, intervals) appear in `results/` and in the playground
  data files.
- **Retrieved:** 2026-11-12.

## Everything else is simulated or hand-built

- The peeking and Thompson-sampling results are simulations with fixed
  seeds (`src/bayesab/simulate.py`); no real experiment data is used.
- The 30 A/B summaries in the LLM check are written by hand
  (`src/bayesab/items.py`) to cover specific situations; they are not
  measurements from real products. The numbers in each item are the
  whole item — the ground truth is computed from them by this repo's
  calculator.
