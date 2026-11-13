"""Download the Cookie Cats A/B test data into data/.

The dataset is "Mobile Games: A/B Testing" by Yufeng Sui on Kaggle
(https://www.kaggle.com/datasets/yufengsui/mobile-games-ab-testing),
which hosts the data from the DataCamp project "Mobile Games A/B Testing
with Cookie Cats" (https://www.datacamp.com/projects/184). The Kaggle
page lists the license as "Unknown", so this repo does **not**
redistribute the CSV: data/ is git-ignored and this script is the way in.

Two routes:
1. Kaggle API (recommended): install kaggle, place your API token in
   ~/.kaggle/kaggle.json, then run this script. It calls
   `kaggle datasets download -d yufengsui/mobile-games-ab-testing`.
2. Fallback: the dataset author's GitHub mirror of the same file
   (github.com/yfsui/Mobile-Games-AB-Testing-Project), used only if the
   Kaggle route is unavailable. The file is verified against the known
   shape (90,189 rows) and group counts before it is accepted.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "cookie_cats.csv"
MIRROR_URL = ("https://raw.githubusercontent.com/yfsui/"
              "Mobile-Games-AB-Testing-Project/master/cookie_cats.csv")
EXPECTED_ROWS = 90189
EXPECTED_GROUPS = {"gate_30": 44700, "gate_40": 45489}


def _verify(path: Path) -> bool:
    import csv

    counts: dict[str, int] = {}
    with path.open() as f:
        reader = csv.DictReader(f)
        rows = 0
        for row in reader:
            rows += 1
            counts[row["version"]] = counts.get(row["version"], 0) + 1
    ok = rows == EXPECTED_ROWS and counts == EXPECTED_GROUPS
    print(f"{path}: {rows} rows, groups {counts} -> {'ok' if ok else 'MISMATCH'}")
    return ok


def via_kaggle() -> bool:
    try:
        subprocess.run(
            ["kaggle", "datasets", "download", "-d",
             "yufengsui/mobile-games-ab-testing", "-p", str(ROOT / "data")],
            check=True, capture_output=True, text=True, timeout=300,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"kaggle route unavailable: {exc}")
        return False
    for z in (ROOT / "data").glob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(ROOT / "data")
        z.unlink()
    return DEST.exists()


def via_mirror() -> bool:
    import urllib.request

    print(f"falling back to the author's GitHub mirror:\n  {MIRROR_URL}")
    urllib.request.urlretrieve(MIRROR_URL, DEST)
    return DEST.exists()


def main() -> int:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and _verify(DEST):
        print("already downloaded and verified")
        return 0
    if not via_kaggle() and not via_mirror():
        print("download failed on both routes")
        return 1
    return 0 if _verify(DEST) else 1


if __name__ == "__main__":
    sys.exit(main())
