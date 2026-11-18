"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted."""
    problems: list[str] = []
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {k} is {v}")

    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []
    manifest = pr.get("manifest") or {}
    expected_rows = int(manifest.get("items") or 0) * len(manifest.get("seeds") or [])
    if len(pr_rows) != expected_rows:
        problems.append(f"row count {len(pr_rows)} != manifest {expected_rows}")

    pr_keys_list = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    if len(pr_keys_list) != len(set(pr_keys_list)):
        problems.append("duplicate (item_id, seed) rows in PR")

    base_keys = {(r.get("item_id"), r.get("seed")) for r in base_rows}
    if set(pr_keys_list) != base_keys:
        problems.append("(item_id, seed) set of PR differs from baseline")

    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures non-empty ({len(pr['evaluator_failures'])})")

    base_row_metrics = {
        m["id"] for m in (spec.get("metrics") or [])
        if base_rows and m["id"] in base_rows[0]
    }
    for r in pr_rows:
        for mid in sorted(base_row_metrics):
            if r.get(mid) is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for {mid}")
                break

    base_slices = {(r.get("item_id"), r.get("seed")): sorted(r.get("slices") or []) for r in base_rows}
    for r in pr_rows:
        key = (r.get("item_id"), r.get("seed"))
        if key in base_slices and sorted(r.get("slices") or []) != base_slices[key]:
            problems.append(f"slice tags altered on {key[0]}@{key[1]}")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        pr_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
        for bm in base_spec.get("metrics") or []:
            mid = bm["id"]
            pm = pr_metrics.get(mid)
            if pm is None:
                problems.append(f"spec metric {mid} removed")
                continue
            if bm.get("blocking") and not pm.get("blocking"):
                problems.append(f"spec metric {mid} downgraded from blocking")
            bth, pth = bm.get("threshold") or {}, pm.get("threshold") or {}
            if "max" in bth and ("max" not in pth or pth["max"] > bth["max"]):
                problems.append(f"spec metric {mid} max loosened")
            if "min" in bth and ("min" not in pth or pth["min"] < bth["min"]):
                problems.append(f"spec metric {mid} min loosened")
            if "max_increase" in bth and ("max_increase" not in pth or pth["max_increase"] > bth["max_increase"]):
                problems.append(f"spec metric {mid} max_increase loosened")
            if bth.get("no_significant_drop") and not pth.get("no_significant_drop"):
                problems.append(f"spec metric {mid} dropped no_significant_drop")

        pr_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
        for bs_item in base_spec.get("slices") or []:
            skey = (bs_item["name"], bs_item["metric"])
            ps_item = pr_slices.get(skey)
            if ps_item is None:
                problems.append(f"spec slice {skey[0]}/{skey[1]} removed")
                continue
            if bs_item.get("blocking") and not ps_item.get("blocking"):
                problems.append(f"spec slice {skey[0]}/{skey[1]} downgraded from blocking")
            if "min" in bs_item and ("min" not in ps_item or ps_item["min"] < bs_item["min"]):
                problems.append(f"spec slice {skey[0]}/{skey[1]} min loosened")
            if bs_item.get("no_significant_drop") and not ps_item.get("no_significant_drop"):
                problems.append(f"spec slice {skey[0]}/{skey[1]} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): evaluate per-slice floors and paired bootstrap CIs."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s["metric"]
        a = per_item(pr, metric, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "min" in s and val < s["min"]:
            verdict = "fail"
        if s.get("no_significant_drop") and val is not None:
            b = per_item(base, metric, slice_name=name)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap(
                [a[k] for k in keys],
                [b[k] for k in keys],
                n_resamples=bs.get("n_resamples", 1000),
                rng=bs.get("rng", 2027),
            )
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        sid = f"slice:{name}/{metric}"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        th_str = json.dumps({k: v for k, v in s.items() if k in ("min", "no_significant_drop")})
        lines.append(f"  {sid:<22} {val!s:<8} {th_str:<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
