#!/usr/bin/env python3
"""
List every raw number in report.json free text that build_report.py would reject, with candidate model refs.

    python number_audit.py report.json model.json

For each undeclared number: the path in report.json, the token, and any model fields whose value matches it
(±display precision) — write those as {{ref|fmt}} placeholders. Numbers with no candidate come from outside
the model: declare them in manual_numbers with field and source. Exit code 1 when anything is undeclared.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_report as br  # noqa: E402


def index_model(obj, path="", out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "projection": continue
            index_model(v, f"{path}.{k}" if path else k, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj): index_model(v, f"{path}.{i}", out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append((path, float(obj)))
    return out


def fmt_for(path, model=None):
    try:
        k = br.field_kind(path, model) if model else None
        if k in ("money", "pct", "mult", "months", "month", "int"): return k
    except Exception:
        pass
    if any(k in path for k in ("ltv_cac", "ratio")): return "mult"
    if "payback" in path: return "months"
    if "breakeven" in path: return "month"
    if any(k in path for k in ("_pct", "churn", "expansion", "margin", "take_rate", "repeat")): return "pct"
    if any(k in path for k in ("mrr", "cac", "ltv", "capital", "arpu", "price", "revenue", "cumulative", "budget", "burn", "upfront", "value", "y1", "y2", "y3")): return "money"
    return "int"


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    rep = json.load(open(sys.argv[1])); model = json.load(open(sys.argv[2]))
    idx = index_model(model)
    try:
        bad = br.verify_free_text(rep)
    except ValueError as e:
        print("ERROR:", e); sys.exit(1)
    if not bad:
        print("OK: every number in free text is a placeholder or a declared manual number"); return
    for path, tok, ctx in bad:
        v, half, _ = br._parse_num(tok)
        cands = [(p, x) for p, x in idx if abs(x - v) <= max(half, 0.005 * abs(v))]
        cands += [(p, x) for p, x in idx if 0 < abs(x) <= 100 and abs(x / 100 - v) <= half and (p, x) not in cands]
        print(f"[{path}] {tok!r}   …{ctx}…")
        if cands:
            for p, x in cands[:4]: print(f"      → {{{{{p}|{fmt_for(p, model)}}}}}   (= {x:g})")
        else:
            print(f"      → no model field matches: declare in manual_numbers {{value, field, source, where: [\"{path}\"], context: \"…{ctx.strip()[:40]}…\"}}")
    print(f"\n{len(bad)} undeclared number(s)")
    sys.exit(1)


if __name__ == "__main__":
    main()
