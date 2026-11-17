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
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    problems: list[str] = []
    metrics = pr.get("metrics") or {}
    for k, v in metrics.items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is non-finite ({v})")

    if pr.get("evaluator_failures"):
        problems.append(f"non-empty evaluator_failures ({len(pr['evaluator_failures'])})")

    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []
    manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    expected_rows = int(manifest.get("items", 0)) * len(manifest.get("seeds") or [])
    if len(pr_rows) != expected_rows:
        problems.append(f"row count {len(pr_rows)} != manifest items*seeds {expected_rows}")
    if len(pr_rows) != len(base_rows):
        problems.append(f"row count {len(pr_rows)} != baseline {len(base_rows)}")
    if set(manifest.get("seeds") or []) != set(base_manifest.get("seeds") or []) or len(
        manifest.get("seeds") or []
    ) != len(base_manifest.get("seeds") or []):
        problems.append("manifest seeds differ from baseline")

    seen_keys: set[tuple] = set()
    dups: list[tuple] = []
    for r in pr_rows:
        key = (r.get("item_id"), r.get("seed"))
        if key in seen_keys:
            dups.append(key)
        seen_keys.add(key)
    if dups:
        problems.append(f"duplicate (item_id, seed) rows: {dups[:3]}")

    base_keys = {(r.get("item_id"), r.get("seed")) for r in base_rows}
    if seen_keys != base_keys:
        problems.append(
            f"(item_id, seed) set differs from baseline "
            f"(missing={len(base_keys - seen_keys)}, extra={len(seen_keys - base_keys)})"
        )

    graded_ids = [m["id"] for m in (spec.get("metrics") or []) if m["id"] in GRADERS]
    for r in pr_rows:
        for mid in graded_ids:
            val = r.get(mid)
            if val is None or (isinstance(val, float) and not math.isfinite(val)):
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} missing/invalid {mid}")
                break

    base_slices = {r.get("item_id"): sorted(r.get("slices") or []) for r in base_rows}
    tampered_slices: list[str] = []
    for r in pr_rows:
        iid = r.get("item_id")
        if iid in base_slices and sorted(r.get("slices") or []) != base_slices[iid]:
            if iid not in tampered_slices:
                tampered_slices.append(str(iid))
    if tampered_slices:
        problems.append(f"slice tags differ from baseline for items: {tampered_slices[:5]}")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        pr_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
        for bm in base_spec.get("metrics") or []:
            mid = bm["id"]
            if mid not in pr_metrics:
                problems.append(f"ratchet: metric {mid} removed")
                continue
            pm = pr_metrics[mid]
            if bm.get("blocking") and not pm.get("blocking"):
                problems.append(f"ratchet: metric {mid} became non-blocking")
            bth = bm.get("threshold") or {}
            pth = pm.get("threshold") or {}
            if "min" in bth and ("min" not in pth or pth["min"] < bth["min"]):
                problems.append(f"ratchet: metric {mid} min loosened ({pth.get('min')} < {bth['min']})")
            if "max" in bth and ("max" not in pth or pth["max"] > bth["max"]):
                problems.append(f"ratchet: metric {mid} max loosened ({pth.get('max')} > {bth['max']})")
            if "max_increase" in bth and (
                "max_increase" not in pth or pth["max_increase"] > bth["max_increase"]
            ):
                problems.append(
                    f"ratchet: metric {mid} max_increase loosened ({pth.get('max_increase')} > {bth['max_increase']})"
                )
            if bth.get("no_significant_drop") and not pth.get("no_significant_drop"):
                problems.append(f"ratchet: metric {mid} dropped no_significant_drop")

        pr_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
        for bs in base_spec.get("slices") or []:
            skey = (bs["name"], bs["metric"])
            if skey not in pr_slices:
                problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} removed")
                continue
            ps = pr_slices[skey]
            if bs.get("blocking") and not ps.get("blocking"):
                problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} became non-blocking")
            if "min" in bs and ("min" not in ps or ps["min"] < bs["min"]):
                problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} min loosened")
            if "max" in bs and ("max" not in ps or ps["max"] > bs["max"]):
                problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} max loosened")
            if bs.get("no_significant_drop") and not ps.get("no_significant_drop"):
                problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, mid = s["name"], s["metric"]
        a = per_item(pr, mid, slice_name=name)
        b = per_item(base, mid, slice_name=name)
        val = (sum(a.values()) / len(a)) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        else:
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if "max" in s and val > s["max"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(f"slice:{name}/{mid}")
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        val_str = f"{round(val, 4)}" if val is not None else "None"
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        lines.append(f"  slice:{name + '/' + mid:<18} {val_str:<8} {json.dumps(th):<38} {note:<28} {label}")
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
