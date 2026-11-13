"""Run the LLM check on Together AI (OpenAI-compatible).

Design rules, shared with the other projects in this portfolio:

* The API key comes from the environment variable TOGETHER_API_KEY (a
  git-ignored local .env file is allowed). Inside Muse, a credential
  surrogate for the connected Together account is used instead: the
  surrogate is not the real key; Muse's egress layer swaps in the real
  key for api.together.xyz. The key is never printed or logged.
* Runs are resumable: a run's ID is (model, item_id, mode); IDs already in
  the output file are skipped.
* Every call records the model ID returned, the seed, the temperature, the
  finish reason, token usage, latency, and the full raw text.
* --dry-run writes placeholder rows to outputs/dry_run.jsonl only. A real
  run refuses to start if the real output file holds placeholder rows.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

BASE_URL = "https://api.together.xyz/v1"
ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "prompts"

TEMPERATURE = 0.7
MAX_TOKENS = 4000


def _surrogate_key() -> str | None:
    import sys

    bin_dir = "/opt/muse/skills/custom-connector-setup/bin"
    try:
        if bin_dir not in sys.path:
            sys.path.insert(0, bin_dir)
        from dynamic_credentials import dynamic_credential_entry

        entry = dynamic_credential_entry("custom.together", "access_token")
        return str(entry["surrogate"])
    except Exception:
        return None


def get_client():
    from dotenv import load_dotenv
    from openai import OpenAI

    # Some environments export NO_PROXY entries (e.g. "[::1]") that the
    # pinned httpx cannot parse when building proxy patterns, which makes
    # the OpenAI client constructor fail before any request is made.
    # Drop bracketed IPv6 entries in-process; routing is unaffected.
    for var in ("NO_PROXY", "no_proxy"):
        raw = os.environ.get(var)
        if raw and "[" in raw:
            kept = [p for p in raw.split(",") if "[" not in p and p.strip()]
            os.environ[var] = ",".join(kept) or "localhost"

    load_dotenv(ROOT / ".env")
    key = os.environ.get("TOGETHER_API_KEY") or _surrogate_key()
    if not key:
        raise RuntimeError(
            "TOGETHER_API_KEY is not set and no connected Together account "
            "was found."
        )
    return OpenAI(api_key=key, base_url=BASE_URL)


def render_prompt(mode: str, item: dict) -> str:
    template = (PROMPTS / f"{mode}.md").read_text()
    return template.format(
        metric=item["metric"],
        context=item["context"],
        n_a=item["n_a"], x_a=item["x_a"],
        n_b=item["n_b"], x_b=item["x_b"],
        rate_a_pct=f"{100 * item['rate_a']:.2f}",
        rate_b_pct=f"{100 * item['rate_b']:.2f}",
    )


def _run_id(model: str, item_id: str, mode: str) -> str:
    return f"{model}|{item_id}|{mode}"


def _existing_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if path.exists():
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("dry_run"):
                    raise RuntimeError(
                        f"{path} contains dry-run placeholder rows. Move "
                        "or delete it before starting a real run."
                    )
                ids.add(row["run_id"])
    return ids


def _one_call(client, model: str, prompt: str, seed: int) -> dict:
    started = time.time()
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                seed=seed,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            choice = resp.choices[0]
            usage = resp.usage
            return {
                "status": "ok",
                "model_returned": resp.model,
                "text": choice.message.content or "",
                "finish_reason": choice.finish_reason,
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
                "latency_s": round(time.time() - started, 3),
                "attempts": attempt + 1,
            }
        except Exception as exc:  # noqa: BLE001 - record and retry any API error
            last_error = exc
            time.sleep(2 ** attempt)
    return {
        "status": "error",
        "model_returned": None,
        "text": "",
        "finish_reason": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "latency_s": round(time.time() - started, 3),
        "attempts": 3,
        "error": f"{type(last_error).__name__}: {last_error}",
    }


def run_batch(models: list[str], item_ids: list[str], modes: list[str],
              out_path: Path, dry_run: bool = False,
              seed_base: int = 20261112) -> list[dict]:
    from .items import load_items

    items = {it["id"]: it for it in load_items()}
    client = None if dry_run else get_client()
    done = set() if dry_run else _existing_ids(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written: list[dict] = []
    with out_path.open("a") as f:
        for model in models:
            for item_id in item_ids:
                for mode in modes:
                    rid = _run_id(model, item_id, mode)
                    if rid in done:
                        continue
                    item = items[item_id]
                    prompt = render_prompt(mode, item)
                    seed = seed_base + abs(hash(rid)) % 100_000
                    if dry_run:
                        row = {
                            "run_id": rid, "dry_run": True, "status": "dry_run",
                            "model_requested": model, "item_id": item_id,
                            "mode": mode, "seed": seed,
                            "temperature": TEMPERATURE, "text": "<placeholder>",
                            "model_returned": None, "finish_reason": None,
                            "prompt_tokens": None, "completion_tokens": None,
                            "latency_s": 0.0,
                        }
                    else:
                        result = _one_call(client, model, prompt, seed)
                        row = {
                            "run_id": rid, "status": result["status"],
                            "model_requested": model, "item_id": item_id,
                            "mode": mode, "seed": seed,
                            "temperature": TEMPERATURE,
                            "text": result["text"],
                            "model_returned": result["model_returned"],
                            "finish_reason": result["finish_reason"],
                            "prompt_tokens": result["prompt_tokens"],
                            "completion_tokens": result["completion_tokens"],
                            "latency_s": result["latency_s"],
                            "attempts": result["attempts"],
                        }
                        if result["status"] == "error":
                            row["error"] = result["error"]
                    f.write(json.dumps(row) + "\n")
                    f.flush()
                    written.append(row)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--items", nargs="+", default=None,
                        help="item IDs; default: all 30")
    parser.add_argument("--modes", nargs="+", default=["direct", "code"],
                        choices=["direct", "code"])
    parser.add_argument("--out", default="outputs/llmcheck_runs.jsonl")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from .items import load_items

    item_ids = args.items or [it["id"] for it in load_items()]
    out = ROOT / ("outputs/dry_run.jsonl" if args.dry_run else args.out)
    rows = run_batch(args.models, item_ids, args.modes, out,
                     dry_run=args.dry_run)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
