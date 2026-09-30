"""List benchmark-library entries that should not carry a report row as they are: unverified, stale (> 24 months), or without a URL.

    python scripts/lib_audit.py            # table of flagged entries
    python scripts/lib_audit.py --all      # every entry with its status

Run it before research so the research step knows which entries to replace first."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from financial_model import _stale, library  # noqa: E402


def main():
    lib = library(); show_all = "--all" in sys.argv
    rows = []
    for k, e in lib.items():
        flags = []
        if e.get("verified") is not True and e.get("tier") not in ("method", "derived"): flags.append("unverified")
        if _stale(e.get("date")): flags.append("stale")
        if not e.get("url") and e.get("tier") in ("primary", "survey"): flags.append("no url")
        if flags or show_all:
            rows.append((k, e.get("tier"), e.get("date"), ", ".join(flags) or "ok"))
    w = max(len(r[0]) for r in rows) if rows else 10
    print(f"{'id':<{w}}  {'tier':<9} {'date':<8} status")
    for k, t, dt, f in sorted(rows, key=lambda r: (r[3] == "ok", r[0])): print(f"{k:<{w}}  {str(t):<9} {str(dt):<8} {f}")
    print(f"\n{sum(1 for r in rows if r[3] != 'ok')} of {len(lib)} entries flagged")


if __name__ == "__main__":
    main()
