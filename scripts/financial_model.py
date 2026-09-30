#!/usr/bin/env python3
"""
Deterministic startup financial model (startup-viability-check) — founder case vs market case.

Usage:
    python financial_model.py input.json            # markdown summary
    python financial_model.py input.json --json     # full JSON

────────────────────────────────────────────────────────────────────────
THE IDEA

The founder brings numbers: some measured, most assumed. The market brings numbers too: benchmarks, comparables,
published prices. The model runs the SAME business twice — once on the founder's numbers (the founder case) and
once on the market's (the market case) — and shows what the difference does to revenue, unit economics, break-even
and capital need. The bridge then answers "which of the founder's deviations from the market matters most to
prove": starting from the market case, one assumption at a time is replaced by the founder's number.

Around the market case, a pessimistic and an optimistic edge show the uncertainty of the benchmarks themselves.

────────────────────────────────────────────────────────────────────────
INPUT SCHEMA — one revenue line (money in one currency; percentages 0–100; every number must be numeric, not text)

{
  "name": "Placement",
  "revenue_unit": "subscription" | "project" | "transactional" | "one_off",
  "months": 36,                         # horizon, integer 12..120
  "assumptions": {
    "<domain>": {
      "founder": 59,                    # the founder's number (a point). null/absent → filled from the market value (flagged)
      "market":  [40, 80],              # benchmark / comparable: a point or [low, high]; the market case uses the mid,
                                        #   the pessimistic/optimistic edges use low/high. null/absent → founder's number (flagged "unverified")
      "status":  "observed" | "founder_stated" | "founder_guess",   # provenance of the FOUNDER number (never upgraded by the model)
      "source":  "price.validation_tools.2026 · primary"           # provenance of the MARKET number — required when market is given
    }
  },
  ...
}

Domains by revenue unit (all percentages in %):
  subscription   pricing (per customer-month) · gross_margin · monthly_churn · expansion (optional, % per month)
  project        project_value · projects_per_year · gross_margin · monthly_churn · expansion (optional)
  transactional  gmv_per_customer_month · take_rate · gross_margin · monthly_churn · expansion (optional)
  one_off        pricing (per purchase) · gross_margin · repeat_rate · (repeat_interval_months is a scalar, below)
  every unit     new_customers_per_month (full-capacity arrivals) · fte_cost (per FTE per month; 0 allowed)
                 cac  — unless growth.motion == "paid", where the domain is monthly_budget and CAC = budget / new customers

Scalars (one value, not compared):
  "growth": {"motion": ..., "ramp_mid_month": 4, "ramp_k": 1.0, "sales_cycle_months": 0, "funnel": [{"step","value","source"}]},
  "channels": [{"name","customers_per_month","cac"}],   # optional; volume-weighted CAC for the founder case when no cac assumption is given
  "fte": 2, "fixed_costs_monthly": 0, "upfront_investment": 0, "free_months": 0 (≤ 24, retention units only),
  "starting_customers": 0, "starting_mrr": 0 (post-revenue, both together), "repeat_interval_months": 6 (one_off),
  "founder_time_cost_per_customer": 0,  # value of UNPAID founder hours spent per new customer (hours × opportunity cost / 160). NOT cash:
                                        #   it never enters the cash flow or the capital need; it produces ltv_cac_incl_time and payback_incl_time
                                        #   next to the cash-based ratios. If the founders draw a salary that sits in fte/shared cost, leave this 0.
  "comparable_benchmark": {"segment_size": 400, "comparable_penetration_pct": [3, 8]}

  "funding_path": "bootstrap" | "pre_seed" | "seed" | "series_a"   # REQUIRED at top level: the market-case capital need is read against a VERIFIED
                                                                     #   typical-round entry for this path; "currency": "EUR" (REQUIRED, top level) and optional
                                                                     #   "fx_rates": {"USD_per_EUR": 1.08} when the benchmark is in another currency. Without a
                                                                     #   verified entry / known currency / rate the comparison is reported as "unavailable".
  "unit_of_sale": "2-hour online AI workshop for agency teams"      # what exactly is sold; the market value of `pricing` must be for THIS format

Multiple lines:  {"startup": "X", "funding_path": "...", "lines": [ {...}, {...} ], "shared_fixed_monthly": 3000}
  Team cost shared by the lines goes in shared_fixed_monthly, not in one line's fte — otherwise that line's unit economics
  and bridge carry the whole team and the other line's look free.

Market values must be for the SAME product the founder sells (same format, same unit of sale). A benchmark for a different
format (a full-day workshop when the founder sells a two-hour one) is not the market column — it is a repricing experiment.
Source strings that name a library entry (`churn.saas.smb.2026`) are checked against references/benchmarks.json.
Validation refuses: non-numeric values, CAC or budget ≤ 0, price ≤ 0, a reversed market range, penetration low ≤ 0,
fte > 0 with cost 0 (or the reverse), a channel table under a paid motion, a founder cac that contradicts the channel table,
sales lag ≥ horizon, a ramp so steep that exp() overflows, an unknown motion, a missing founder status.

────────────────────────────────────────────────────────────────────────
OUTPUT

  cases.founder / cases.market / cases.pessimistic / cases.optimistic — full runs (inputs, unit_economics, milestones,
      breakeven_month, peak_capital_need, comparable_benchmark, projection)
  comparison[] — one row per domain: founder value, market value (mid, low, high), status, source, gap (ratio),
      fill flag ("filled_from_market" | "unverified" | null)
  bridge[] — market case with ONE domain set to the founder's number: outcome and delta vs the market case,
      ranked by |Δ peak capital need|. Only domains where founder ≠ market. Rows are NOT additive: assumptions interact
      (the founder-case − market-case difference is not the sum of the rows). Under a paid motion a joint row
      "monthly_budget+new_customers_per_month" is added because both move the derived CAC.
  counts — {observed, founder_stated, founder_guess, unverified, filled_from_market, total} for the prose.
  capital_vs_round — market-case capital need against the typical round for funding_path: {path, round_low, round_high, position}
      position ∈ below_round | inside_round | above_round (size only — never a statement that the round can be raised).
  multi-line: combined.<case> plus combined.bridge — every line's bridge rows re-evaluated on COMBINED capital need
      (shared overhead and the other lines at market), which is what ranks the report's stories.
  months; multi-line adds lines{} and combined{} per case.

────────────────────────────────────────────────────────────────────────
MATH (unchanged from earlier versions)

CAC:  paid motion → budget / new customers · channels → Σ(v_i·cac_i)/Σv_i (founder case; the market case uses the
      market cac when given) · otherwise the cac assumption.  Acquisition spend = new customers × CAC each month.
Revenue per customer-month ARPU₀: subscription pricing · project value × projects/yr ÷ 12 · transactional GMV × take rate.
Retention units, cohort-consistent:
  paying(m)  = paying(m−1)(1−churn) + new(m−F)(1−churn)^F          F = free_months
  revenue(m) = revenue(m−1)·q + new(m−F)(1−churn)^F·ARPU₀,  q = (1−churn)(1+expansion); seeded by starting_customers / starting_mrr
  LTV        = (1−churn)^F · ARPU₀ · margin · Σ_{t<60−F} q^t     (60-month cap)
  payback    = first month where the cumulative contribution of one customer ≥ CAC (≤ 60, else None)
One-off:  purchases(m) = new(m) + repeat · purchases(m − interval);  LTV = price·margin·Σ_{k·interval<60} repeat^k
Capital:  cumulative cash starts at −upfront_investment; peak_capital_need = max(upfront, −min cumulative).
Ramp:     capacity(m) = full_capacity / (1 + e^(−k(m − mid))); arrivals lag by sales_cycle_months; spend follows capacity.
Comparable benchmark: reference = segment × penetration (3 years) vs bottom-up customers at month 36 (horizon ≥ 36 only).
"""

import json
import math
import sys
from typing import Any

RAMP_MID_DEFAULT = {"paid": 2, "organic": 8, "viral": 6, "plg": 4, "founder_led": 1,
                    "inside_sales": 3, "enterprise": 7, "partner": 6, "developer": 10}
UNITS = ("subscription", "project", "transactional", "one_off")
LTV_HORIZON = 60
CASES = ("founder", "market", "pessimistic", "optimistic")
STATUSES = ("observed", "founder_stated", "founder_guess")
FUNDING_PATHS = {"bootstrap": "bootstrap.capital", "pre_seed": "round.pre_seed.eu", "seed": "round.seed.eu", "series_a": "round.series_a.eu"}
_LIB = None


def library() -> dict:
    """references/benchmarks.json entries by id (empty if the file is not next to the scripts)."""
    global _LIB
    if _LIB is None:
        import os
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "benchmarks.json")
        try:
            _LIB = {e["id"]: e for e in json.load(open(fp, encoding="utf-8"))["entries"]}
        except Exception:
            _LIB = {}
    return _LIB


_LIB_ID = None
MARKET_STATUSES = ("cited", "library", "derived")   # cited = a named comparable/primary figure · library = a benchmarks.json entry · derived = the analyst's own calculation or rule of thumb


def _stale(date_str, months=24) -> bool:
    """True when a library entry's date is older than `months` (YYYY or YYYY-MM)."""
    if not date_str: return False
    import datetime as _dt
    try:
        parts = str(date_str).split("-"); y = int(parts[0]); m = int(parts[1]) if len(parts) > 1 else 6
    except ValueError:
        return False
    now = _dt.date.today()
    return (now.year - y) * 12 + (now.month - m) > months

# domain → (label, better_is_high, kind, bounds)   kind: money | pct | count
DOMAINS = {
    "pricing": ("price", True, "money", (0.01, None)),
    "project_value": ("project value", True, "money", (0.01, None)),
    "projects_per_year": ("projects per client per year", True, "count", (0.01, None)),
    "gmv_per_customer_month": ("GMV per customer per month", True, "money", (0.01, None)),
    "take_rate": ("take rate", True, "pct", (0, 100)),
    "gross_margin": ("gross margin", True, "pct", (0.000001, 100)),
    "monthly_churn": ("monthly churn", False, "pct", (0.0, 99.999999)),
    "expansion": ("expansion", True, "pct", (0, 30)),
    "repeat_rate": ("repeat rate", True, "pct", (0, 99.999999)),
    "cac": ("cost to acquire", False, "money", (0, None)),             # CASH per new customer (tools, ads, events, partner fees). May be 0. Founder hours go in founder_time_cost_per_customer
    "monthly_budget": ("monthly acquisition budget", False, "money", (0.01, None)),
    "new_customers_per_month": ("new customers per month", True, "count", (0.000001, None)),
    "fte_cost": ("cost per FTE per month", False, "money", (0, None)),
}
UNIT_DOMAINS = {
    "subscription": ["pricing", "gross_margin", "monthly_churn", "expansion"],
    "project": ["project_value", "projects_per_year", "gross_margin", "monthly_churn", "expansion"],
    "transactional": ["gmv_per_customer_month", "take_rate", "gross_margin", "monthly_churn", "expansion"],
    "one_off": ["pricing", "gross_margin", "repeat_rate"],
}
OPTIONAL_DOMAINS = {"expansion", "fte_cost"}


def _num(v: Any, name: str, allow_none=False):
    if v is None and allow_none:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
        raise ValueError(f"{name} must be a finite number, got {v!r}")
    return float(v)


def _int(v: Any, name: str, lo: int, hi: int | None = None) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
        raise ValueError(f"{name} must be an integer, got {v!r}")
    v = int(v)
    if v < lo or (hi is not None and v > hi):
        raise ValueError(f"{name} must be between {lo} and {hi if hi is not None else '∞'}, got {v}")
    return v


def ramp_factor(m: float, mid: float, k: float) -> float:
    if k == 0:
        return 1.0
    x = -k * (m - mid)
    if x > 500: return 0.0
    if x < -500: return 1.0
    return 1.0 / (1.0 + math.exp(x))


# ── validation ───────────────────────────────────────────────

def validate(cfg: dict) -> dict:
    if not isinstance(cfg, dict):
        raise ValueError("line config must be an object")
    unit = cfg.get("revenue_unit", "subscription")
    if unit not in UNITS:
        raise ValueError(f"revenue_unit must be one of {UNITS}, got {unit!r}")
    out: dict = {"unit": unit, "name": str(cfg.get("name", "")), "warnings": []}
    out["months"] = _int(cfg.get("months", 36), "months", 12, 120)

    g = cfg.get("growth")
    if not isinstance(g, dict) or "motion" not in g:
        raise ValueError("growth{motion, ...} is required")
    motion = str(g["motion"])
    if motion not in RAMP_MID_DEFAULT:
        raise ValueError(f"growth.motion must be one of {sorted(RAMP_MID_DEFAULT)}, got {motion!r}")
    out["growth"] = {"motion": motion,
                     "ramp_mid": _num(g.get("ramp_mid_month", RAMP_MID_DEFAULT.get(motion, 4)), "growth.ramp_mid_month"),
                     "ramp_k": _num(g.get("ramp_k", 1.0), "growth.ramp_k"),
                     "lag": _int(g.get("sales_cycle_months", 0), "growth.sales_cycle_months", 0, 24),
                     "funnel": list(g.get("funnel", []))}
    if out["growth"]["ramp_k"] < 0 or out["growth"]["ramp_k"] > 20:
        raise ValueError("growth.ramp_k must be within [0, 20]")
    if out["growth"]["ramp_mid"] < 0 or out["growth"]["ramp_mid"] > out["months"]:
        raise ValueError("growth.ramp_mid_month must be within [0, months]")
    if out["growth"]["lag"] >= out["months"]:
        raise ValueError("growth.sales_cycle_months must be shorter than the horizon — otherwise no customer ever arrives")
    if out["growth"]["ramp_k"] * (out["growth"]["ramp_mid"] + out["growth"]["lag"] + 1) > 500:
        raise ValueError("growth.ramp_k × ramp_mid_month is too steep for a spreadsheet exp(); use a smaller k or an earlier midpoint")
    for i, f in enumerate(out["growth"]["funnel"]):
        if not isinstance(f, dict) or not str(f.get("step", "")).strip() or not str(f.get("source", "")).strip():
            raise ValueError(f"growth.funnel[{i}] needs 'step' and 'source'")
    paid = motion == "paid"
    if paid and cfg.get("channels"):
        raise ValueError("a paid motion derives CAC from monthly_budget; a channel table would be ignored — remove one of them")

    # ── assumptions: founder / market per domain
    A = cfg.get("assumptions")
    if not isinstance(A, dict):
        raise ValueError("assumptions{} is required: one entry per domain with 'founder' and/or 'market'")
    needed = UNIT_DOMAINS[unit] + ["new_customers_per_month", "fte_cost"] + (["monthly_budget"] if paid else ["cac"])
    unknown = set(A) - set(DOMAINS)
    if unknown:
        raise ValueError(f"unknown assumption domain(s) {sorted(unknown)}; allowed: {sorted(DOMAINS)}")
    wrong_unit = set(A) - set(needed)
    if wrong_unit:
        raise ValueError(f"assumption(s) {sorted(wrong_unit)} do not apply to revenue_unit={unit!r}"
                         + (" with a paid motion (use monthly_budget, CAC is derived)" if paid and "cac" in wrong_unit else ""))
    channels = cfg.get("channels") or []
    if not isinstance(channels, list): raise ValueError("channels must be a list")
    for ch in channels:
        if not isinstance(ch, dict) or "customers_per_month" not in ch:
            raise ValueError(f"channel {ch!r} needs customers_per_month")
        if _num(ch["customers_per_month"], f"channel {ch.get('name')} customers_per_month") < 0:
            raise ValueError("channel customers_per_month cannot be negative")
        c = _num(ch.get("cac"), f"channel {ch.get('name')} cac", allow_none=True)
        if c is not None and c < 0: raise ValueError("channel cac cannot be negative")
    if channels and sum(float(c["customers_per_month"]) for c in channels) <= 0:
        raise ValueError("channels must add up to a positive number of customers per month")
    if channels and any(c.get("cac") is None for c in channels):
        raise ValueError("every channel needs its own cac — the channel table is the founder's CAC and must be complete")

    dom: dict = {}
    for d in needed:
        spec = A.get(d)
        label, better_high, kind, (lo_b, hi_b) = DOMAINS[d]
        if spec is None:
            if d in OPTIONAL_DOMAINS:
                spec = {"founder": 0.0, "market": 0.0, "status": "founder_stated", "source": "default 0"}
            elif d == "cac" and channels and all(c.get("cac") is not None for c in channels):
                spec = {"founder": None, "market": None}
            else:
                raise ValueError(f"assumptions.{d} is required for revenue_unit={unit!r}" + (" (paid motion)" if d == "monthly_budget" else ""))
        if not isinstance(spec, dict):
            raise ValueError(f"assumptions.{d} must be an object with founder/market")
        f = _num(spec.get("founder"), f"assumptions.{d}.founder", allow_none=True)
        mk = spec.get("market")
        if isinstance(mk, list):
            if len(mk) != 2: raise ValueError(f"assumptions.{d}.market must be a number or [low, high]")
            m_lo, m_hi = _num(mk[0], f"assumptions.{d}.market[0]"), _num(mk[1], f"assumptions.{d}.market[1]")
            if m_lo > m_hi: raise ValueError(f"assumptions.{d}.market is [high, low]; write it as [low, high]")
        else:
            m_lo = m_hi = _num(mk, f"assumptions.{d}.market", allow_none=True)
        status = spec.get("status")
        if f is not None and status is None:
            raise ValueError(f"assumptions.{d}.status is required when a founder value is given ({STATUSES})")
        if f is not None and status not in STATUSES:
            raise ValueError(f"assumptions.{d}.status must be one of {STATUSES}, got {status!r}")
        source = str(spec.get("source", "") or "").strip()
        if m_lo is not None and not source:
            raise ValueError(f"assumptions.{d}.market is given without a 'source'")
        lib_flags, lib_ids = [], []
        if source and library():
            import re as _re
            families = {i.split(".")[0] for i in library()}
            no_urls = _re.sub(r"https?://\S+|\bwww\.\S+", " ", source)
            for tok in _re.findall(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){1,}\b", no_urls):
                if tok.split(".")[0] in families and tok not in library():
                    raise ValueError(f"assumptions.{d}.source cites library entry {tok!r} which does not exist in references/benchmarks.json")
                if tok in library():
                    e = library()[tok]; lib_ids.append(tok)
                    if e.get("verified") is not True and e.get("tier") not in ("method", "derived"):
                        lib_flags.append("unverified"); out["warnings"].append(f"assumptions.{d}: library entry {tok} is not verified (practitioner consensus, no URL) — the market value is a working estimate until research replaces it")
                    if _stale(e.get("date")):
                        lib_flags.append("stale"); out["warnings"].append(f"assumptions.{d}: library entry {tok} is dated {e.get('date')} — older than 24 months; refresh before it carries a report row")
        m_status = spec.get("market_status")
        if m_status is not None and m_status not in MARKET_STATUSES:
            raise ValueError(f"assumptions.{d}.market_status must be one of {MARKET_STATUSES}")
        if m_status is None and m_lo is not None:   # not stated: infer, and say so in the pack
            derived_words = ("derived", "scaled", "estimate", "funnel", "capacity", "rule of thumb", "assumed", "оцен", "воронк", "расч")
            m_status = "derived" if any(w in source.lower() for w in derived_words) else ("library" if lib_ids else "cited")
        m_currency = spec.get("currency")
        model_ccy = CURRENCY_CODES.get(str(cfg.get("currency") or cfg.get("_currency") or "").strip().upper())
        if m_currency is not None and CURRENCY_CODES.get(str(m_currency).strip().upper()) != model_ccy:
            raise ValueError(f"assumptions.{d}: market value is in {m_currency} but the model currency is {model_ccy!r}; convert it at a recorded rate (say so in 'source') and drop the 'currency' field")
        fill = None
        if f is None and m_lo is None:
            if d == "cac" and channels:
                # both cases derive CAC from the channel table
                w = sum(float(c["customers_per_month"]) * float(c["cac"]) for c in channels) / sum(float(c["customers_per_month"]) for c in channels)
                f = m_lo = m_hi = w; status = "founder_stated"; source = "volume-weighted channel table"; fill = "derived_from_channels"
            else:
                raise ValueError(f"assumptions.{d}: give at least a founder or a market value")
        elif f is None and d == "cac" and channels and all(c.get("cac") is not None for c in channels):
            f = sum(float(c["customers_per_month"]) * float(c["cac"]) for c in channels) / sum(float(c["customers_per_month"]) for c in channels)
            status = "founder_stated"   # the founder's channel table is the founder's number
        elif f is None:
            f = (m_lo + m_hi) / 2; fill = "filled_from_market"; status = "benchmarked"
        elif m_lo is None:
            m_lo = m_hi = f; fill = "unverified"
        if d == "cac" and channels and all(c.get("cac") is not None for c in channels):
            w = sum(float(c["customers_per_month"]) * float(c["cac"]) for c in channels) / sum(float(c["customers_per_month"]) for c in channels)
            if abs(f - w) > 0.005 * max(w, 1):
                raise ValueError(f"assumptions.cac.founder = {f:g} contradicts the channel table (volume-weighted {w:.2f}); give one or the other — the channel table is the founder's CAC")
        for v, nm in ((f, "founder"), (m_lo, "market low"), (m_hi, "market high")):
            if v < lo_b or (hi_b is not None and v > hi_b):
                raise ValueError(f"assumptions.{d}.{nm} = {v:g} is outside the allowed range [{lo_b:g}, {hi_b if hi_b is not None else '∞'}]")
        dom[d] = {"label": label, "kind": kind, "better_high": better_high, "founder": f, "market": (m_lo + m_hi) / 2,
                  "market_low": m_lo, "market_high": m_hi, "status": status, "source": source, "fill": fill,
                  "market_status": m_status, "library_flags": sorted(set(lib_flags))}
    out["dom"] = dom
    out["channels"] = channels
    out["unit_of_sale"] = str(cfg.get("unit_of_sale", "") or "").strip()

    if unit == "one_off":
        out["interval"] = _int(cfg.get("repeat_interval_months", 6), "repeat_interval_months", 1, 120)
    if unit != "one_off":
        ch_, ex_ = dom["monthly_churn"], dom.get("expansion")
        if ex_ and (ex_["market_high"] >= ch_["market_low"] or ex_["founder"] >= ch_["founder"]):
            out["warnings"].append("expansion is as high as churn on at least one edge: revenue per customer would grow forever; LTV is capped at no net growth and the optimistic edge should be read with that in mind")
    if unit != "one_off" and dom["monthly_churn"]["founder"] > 40:
        out["warnings"].append("monthly churn above 40 % — check the contract: a purchase that is not repeated is a one_off unit, not a subscription")

    out["fte"] = _num(cfg.get("fte", 0), "fte"); out["fixed"] = _num(cfg.get("fixed_costs_monthly", 0), "fixed_costs_monthly")
    out["upfront"] = _num(cfg.get("upfront_investment", 0), "upfront_investment")
    out["free_months"] = _int(cfg.get("free_months", 0), "free_months", 0, 24)
    out["time_cost"] = _num(cfg.get("founder_time_cost_per_customer", 0), "founder_time_cost_per_customer")
    if out["time_cost"] < 0: raise ValueError("founder_time_cost_per_customer cannot be negative")
    out["sales_share"] = _num(cfg.get("sales_share_of_payroll", 0), "sales_share_of_payroll")
    if not 0 <= out["sales_share"] <= 1: raise ValueError("sales_share_of_payroll must be within [0, 1] — the share of payroll that is selling (founder hours on sales, SDRs, AEs)")
    out["cash"] = _num(cfg.get("cash_on_hand"), "cash_on_hand", allow_none=True)
    if out["cash"] is not None and out["cash"] < 0: raise ValueError("cash_on_hand cannot be negative")
    out["start_customers"] = _num(cfg.get("starting_customers", 0), "starting_customers")
    out["start_mrr"] = _num(cfg.get("starting_mrr", 0), "starting_mrr")
    for k in ("fte", "fixed", "upfront", "start_customers", "start_mrr"):
        if out[k] < 0: raise ValueError(f"{k} cannot be negative")
    fc = dom["fte_cost"]
    if out["fte"] > 0 and (fc["founder"] <= 0 or fc["market"] <= 0):
        raise ValueError("fte > 0 but fte_cost is 0 — state the cost per FTE (founders' own salaries count) or set fte to 0")
    if out["fte"] == 0 and (fc["founder"] > 0 or fc["market"] > 0):
        raise ValueError("fte_cost is given but fte is 0 — the team cost would silently vanish; set fte or drop fte_cost")
    if out["free_months"] and unit == "one_off":
        raise ValueError("free_months applies to retention units only")
    if unit == "one_off" and (out["start_customers"] or out["start_mrr"]):
        raise ValueError("starting_customers / starting_mrr apply to retention units only")
    if (out["start_customers"] > 0) != (out["start_mrr"] > 0):
        raise ValueError("starting_customers and starting_mrr must be given together (both measured)")

    cb = cfg.get("comparable_benchmark")
    out["comparable"] = None
    if cb:
        seg = _num(cb.get("segment_size"), "comparable_benchmark.segment_size")
        pen = cb.get("comparable_penetration_pct", [1, 3])
        if not isinstance(pen, list) or len(pen) != 2: raise ValueError("comparable_penetration_pct must be [low, high]")
        p_lo, p_hi = _num(pen[0], "penetration"), _num(pen[1], "penetration")
        if seg <= 0 or p_lo <= 0 or p_hi > 100 or p_lo > p_hi: raise ValueError("comparable_benchmark: segment_size > 0 and penetration [low, high] within (0, 100]")
        out["comparable"] = {"segment": seg, "pen": (min(p_lo, p_hi), max(p_lo, p_hi))}
    return out


# ── case values ──────────────────────────────────────────────

def case_values(p: dict, case: str) -> dict:
    """Point value of every domain for a case."""
    v = {}
    for d, s in p["dom"].items():
        if case == "founder": v[d] = s["founder"]
        elif case == "market": v[d] = s["market"]
        elif case == "pessimistic": v[d] = s["market_low"] if s["better_high"] else s["market_high"]
        else: v[d] = s["market_high"] if s["better_high"] else s["market_low"]
    return v


def blended_cac(p: dict, v: dict, case: str) -> tuple[float, str]:
    if "monthly_budget" in v:
        nc = v["new_customers_per_month"]
        return v["monthly_budget"] / nc, "budget / new customers"
    if p["channels"] and case == "founder":
        return v["cac"], "volume-weighted channel table"
    return v["cac"], "assumption"


# ── simulation ───────────────────────────────────────────────

def simulate(p: dict, v: dict, case: str) -> dict:
    unit = p["unit"]; g = p["growth"]; months = p["months"]
    margin = v["gross_margin"] / 100
    new_full = v["new_customers_per_month"]
    cac, cac_method = blended_cac(p, v, case)
    payroll = p["fte"] * v["fte_cost"]; burn_fixed = payroll + p["fixed"]
    F = p["free_months"]

    def arrivals(m): eff = m - g["lag"]; return new_full * ramp_factor(eff, g["ramp_mid"], g["ramp_k"]) if eff >= 1 else 0.0
    def spending(m): return new_full * ramp_factor(m, g["ramp_mid"], g["ramp_k"])

    rows = []; cum = -p["upfront"]; min_cash = cum; breakeven = None
    raw = []   # unrounded (gross_profit, marketing, cumulative) per month — the breakdown and the trough are taken from these, never from rounded rows
    nets = []
    if unit == "one_off":
        price = v["pricing"]; r = v["repeat_rate"] / 100; iv = p["interval"]
        contribution = price * margin
        n_cycles = (LTV_HORIZON + iv - 1) // iv
        S1 = sum(r ** k for k in range(n_cycles)); ltv = contribution * S1; ltv_uncapped = contribution / (1 - r)
        arpu_be3 = 3 * cac / (margin * S1) if cac > 0 else 0.0
        purchases = []
        for m in range(1, months + 1):
            new = arrivals(m); rep = r * purchases[m - 1 - iv] if m - 1 - iv >= 0 else 0.0
            pur = new + rep; purchases.append(pur); revenue = pur * price
            mkt = spending(m) * cac; net = revenue * margin - mkt - burn_fixed
            cum += net; min_cash = min(min_cash, cum); raw.append((revenue * margin, mkt, cum)); nets.append(net)
            rows.append({"month": m, "new_customers": round(new, 2), "customers": round(pur, 1), "units_label": "purchases",
                         "mrr": round(revenue, 0), "gross_profit": round(revenue * margin, 0), "marketing": round(mkt, 0), "payroll": round(payroll, 0), "fixed": round(p["fixed"], 0),
                         "net_cash_flow": round(net, 0), "cumulative": round(cum, 0)})
        arpu0 = price
        def pb_oneoff(target):
            cum_c, k = 0.0, 0
            while k * iv < LTV_HORIZON:
                cum_c += contribution * r ** k
                if cum_c >= target - 1e-9: return k * iv + 1
                k += 1
            return None
        payback = pb_oneoff(cac); payback_time = pb_oneoff(cac + p["time_cost"])
        inputs = {"price": price, "repeat_rate_pct": r * 100, "repeat_interval_months": iv}
    else:
        if unit == "project": arpu0 = v["project_value"] * v["projects_per_year"] / 12
        elif unit == "transactional": arpu0 = v["gmv_per_customer_month"] * v["take_rate"] / 100
        else: arpu0 = v["pricing"]
        churn = v["monthly_churn"] / 100; exp_ = v.get("expansion", 0.0) / 100
        q = (1 - churn) * (1 + exp_); contribution = arpu0 * margin; surv = (1 - churn) ** F
        q_ltv = min(q, 1.0)   # lifetime value never assumes a customer that grows forever
        S = surv * sum(q_ltv ** t for t in range(max(LTV_HORIZON - F, 0)))
        ltv = contribution * S; ltv_uncapped = None
        arpu_be3 = (3 * cac / (margin * S) if S > 0 else None) if cac > 0 else 0.0
        customers = p["start_customers"]; revenue = p["start_mrr"]
        for m in range(1, months + 1):
            new = arrivals(m); paying_new = arrivals(m - F) * surv if m - F >= 1 else 0.0
            customers = customers * (1 - churn) + paying_new
            revenue = revenue * q + paying_new * arpu0
            mkt = spending(m) * cac; net = revenue * margin - mkt - burn_fixed
            cum += net; min_cash = min(min_cash, cum); raw.append((revenue * margin, mkt, cum)); nets.append(net)
            rows.append({"month": m, "new_customers": round(new, 2), "customers": round(customers, 1), "units_label": "customers",
                         "arpu": round(revenue / customers, 2) if customers > 0 else 0.0,
                         "mrr": round(revenue, 0), "gross_profit": round(revenue * margin, 0), "marketing": round(mkt, 0), "payroll": round(payroll, 0), "fixed": round(p["fixed"], 0),
                         "net_cash_flow": round(net, 0), "cumulative": round(cum, 0)})
        def pb_ret(target):
            cum_c = 0.0
            for t in range(max(LTV_HORIZON - F, 0)):
                cum_c += surv * contribution * q_ltv ** t
                if cum_c >= target - 1e-9: return F + t + 1
            return None
        payback = pb_ret(cac); payback_time = pb_ret(cac + p["time_cost"])
        inputs = {"arpu0": round(arpu0, 2), "monthly_churn_pct": churn * 100, "expansion_pct": exp_ * 100, "free_months": F,
                  "starting_customers": p["start_customers"], "starting_mrr": p["start_mrr"]}
        if unit == "project": inputs.update(project_value=v["project_value"], projects_per_year=v["projects_per_year"])
        if unit == "transactional": inputs.update(gmv_per_customer_month=v["gmv_per_customer_month"], take_rate_pct=v["take_rate"])
    inputs.update({"revenue_unit": unit, "blended_cac": round(cac, 2), "cac_method": cac_method, "sales_share_of_payroll": p["sales_share"], "founder_time_cost_per_customer": p["time_cost"], "gross_margin_pct": margin * 100,
                   "new_customers_per_month_full": new_full, "monthly_fixed_burn": burn_fixed, "upfront_investment": p["upfront"],
                   "fte_cost": v["fte_cost"]})
    if "monthly_budget" in v: inputs["monthly_budget"] = v["monthly_budget"]

    def at(mo): return rows[mo - 1] if mo <= len(rows) else rows[-1]
    milestones = {f"m{k}": at(k) for k in (12, 24, 36) if k <= months}; milestones["end"] = dict(at(months))
    comp = None
    if p["comparable"] and unit == "one_off":
        comp = {"note": "comparable benchmark skipped: one-off units count purchases, not customers"}
    elif p["comparable"] and months < 36:
        comp = {"note": f"comparable benchmark skipped: the reference is a 3-year figure and the horizon is {months} months"}
    elif p["comparable"]:
        pen = {"founder": sum(p["comparable"]["pen"]) / 2, "market": sum(p["comparable"]["pen"]) / 2,
               "pessimistic": p["comparable"]["pen"][0], "optimistic": p["comparable"]["pen"][1]}[case] / 100
        ref = p["comparable"]["segment"] * pen; c36 = at(36)["customers"]
        ratio = c36 / ref if ref > 0 else None
        pos = "no_reference" if ratio is None else ("above_comparables" if ratio > 1 else ("far_below_comparables" if ratio < 0.1 else "within_range"))
        comp = {"segment_size": p["comparable"]["segment"], "comparable_penetration_pct": pen * 100, "reference_customers_3y": round(ref, 0),
                "bottom_up_customers_m36": c36, "implied_share_pct": round(c36 / p["comparable"]["segment"] * 100, 3),
                "ratio_to_reference": round(ratio, 3) if ratio is not None else None, "position": pos}
    # break-even: the first month from which the monthly result stays ≥ 0 for the rest of the horizon (a single positive month is not break-even)
    breakeven = None
    for m in range(len(nets), 0, -1):
        if nets[m - 1] >= 0: breakeven = m
        else: break
    # cash trough: the month of the deepest cumulative deficit; capital need = upfront + everything spent until then, net of gross profit (unrounded sums)
    trough_m = min(range(len(raw)), key=lambda i: raw[i][2]) + 1 if raw else 0
    if raw and raw[trough_m - 1][2] >= -p["upfront"]: trough_m = 0   # cash never dips below the upfront outlay: the need IS the upfront
    upto = raw[:trough_m]
    breakdown = {"upfront": round(p["upfront"], 0), "payroll": round(payroll * trough_m, 0), "marketing": round(sum(r[1] for r in upto), 0),
                 "fixed": round(p["fixed"] * trough_m, 0), "gross_profit_offset": round(sum(r[0] for r in upto), 0), "trough_month": trough_m,
                 "truncated": trough_m == months and months > 0 and nets[-1] < 0}   # still falling at the horizon: the need is understated
    peak = round(max(p["upfront"], -min_cash, 0.0), 0)
    lc = round(ltv / cac, 2) if cac > 0 else None
    # fully-loaded CAC: cash CAC + the selling share of payroll per new customer at full ramp (sales-led motions hide their CAC in salaries)
    cac_loaded = cac + (payroll * p["sales_share"] / new_full if new_full > 0 else 0.0)
    lc_loaded = round(ltv / cac_loaded, 2) if cac_loaded > 0 else None
    payback_loaded = (pb_oneoff(cac_loaded) if unit == "one_off" else pb_ret(cac_loaded)) if cac_loaded > 0 else payback
    lc_h, pb_h = (lc_loaded, payback_loaded) if p["sales_share"] > 0 else (lc, payback)   # the headline ratio is the loaded one when a selling share is given
    # cash-out: with cash_on_hand, the first month cumulative cash falls below −cash (upfront already inside cumulative)
    # cash recovery: first month after the trough when cumulative cash is back at or above zero (the outlay is earned back)
    cash_rec = next((i + 1 for i, r in enumerate(raw) if i + 1 > trough_m and r[2] >= 0), None) if trough_m else (1 if raw and raw[0][2] >= 0 else None)
    cash_out = None
    if p["cash"] is not None:
        cash_out = next((i + 1 for i, r in enumerate(raw) if r[2] < -p["cash"]), None)
    flags = []   # traffic lights; the thresholds are the usual investor rules of thumb (headline = loaded ratio when given)
    if lc_h is not None and lc_h < 1: flags.append({"id": "ltv_cac_negative", "level": "red"})
    elif lc_h is not None and lc_h < 3: flags.append({"id": "ltv_cac_thin", "level": "amber"})
    if pb_h is None or pb_h > 18: flags.append({"id": "slow_payback", "level": "amber"})
    if breakeven is None: flags.append({"id": "no_breakeven", "level": "red"})
    if cash_out is not None: flags.append({"id": "cash_out", "level": "red"})
    if (lc_h is None or lc_h > 5) and breakeven and breakeven <= 12 and cash_out is None: flags.append({"id": "strong_economics", "level": "green"})
    return {"case": case, "inputs": inputs, "months": months,
            "unit_economics": {"ltv": round(ltv, 2), "ltv_horizon_months": LTV_HORIZON, "ltv_uncapped": round(ltv_uncapped, 2) if ltv_uncapped is not None else None,
                               "ltv_cac": round(ltv / cac, 2) if cac > 0 else None, "cash_cac_zero": cac <= 0, "arpu_actual": round(arpu0, 2),
                               "cac_loaded": round(cac_loaded, 2), "ltv_cac_loaded": lc_loaded, "payback_loaded": payback_loaded, "sales_share_of_payroll": p["sales_share"],
                               "ltv_cac_headline": lc_h, "payback_headline": pb_h,
                               "arpu_for_ltv_cac_3": round(arpu_be3, 2) if arpu_be3 is not None else None, "payback_months": payback,
                               "ltv_cac_incl_time": round(ltv / (cac + p["time_cost"]), 2) if cac + p["time_cost"] > 0 else None, "payback_incl_time": payback_time,
                               "payback_note": None if payback else "lifetime contribution does not cover CAC within 60 months"},
            "breakeven_month": breakeven, "peak_capital_need": peak, "capital_breakdown": breakdown, "flags": flags,
            "cash_on_hand": p["cash"], "cash_out_month": cash_out, "cash_recovery_month": cash_rec,
            "milestones": milestones, "growth": {"motion": g["motion"], "ramp_mid_month": g["ramp_mid"], "sales_cycle_months": g["lag"], "funnel": g["funnel"]},
            "comparable_benchmark": comp, "warnings": p["warnings"], "projection": rows}


# ── comparison & bridge ──────────────────────────────────────

def comparison(p: dict) -> list:
    rows = []
    for d, s in p["dom"].items():
        f, m = s["founder"], s["market"]
        if f == m: gap = None
        elif min(f, m) > 0: gap = round(max(f, m) / min(f, m), 2)
        else: gap = "inf"
        rows.append({"domain": d, "label": s["label"], "kind": s["kind"], "founder": f, "market": m, "market_low": s["market_low"], "market_high": s["market_high"],
                     "status": s["status"], "source": s["source"], "fill": s["fill"], "gap_ratio": gap,
                     "market_status": s.get("market_status"), "library_flags": s.get("library_flags", []),
                     "founder_better": ((f > m) == s["better_high"]) if f != m else None})
    return rows


def bridge(p: dict, market_case: dict) -> list:
    """From the market case, replace ONE domain by the founder's number; report the outcome and the delta."""
    base_v = case_values(p, "market"); out = []
    for d, s in p["dom"].items():
        if s["fill"] or s["founder"] == s["market"]: continue
        v = dict(base_v); v[d] = s["founder"]
        alt = simulate(p, v, "market")
        dl = lambda a, b: None if a is None or b is None else round(a - b, 2)
        out.append({"domain": d, "label": s["label"], "kind": s["kind"], "market": s["market"], "founder": s["founder"], "status": s["status"], "source": s["source"],
                    "peak_capital_need": {"market": market_case["peak_capital_need"], "if_founder_right": alt["peak_capital_need"], "delta": dl(alt["peak_capital_need"], market_case["peak_capital_need"])},
                    "breakeven_month": {"market": market_case["breakeven_month"], "if_founder_right": alt["breakeven_month"]},
                    "revenue_end": {"month": p["months"], "market": market_case["milestones"]["end"]["mrr"], "if_founder_right": alt["milestones"]["end"]["mrr"],
                                    "delta": dl(alt["milestones"]["end"]["mrr"], market_case["milestones"]["end"]["mrr"])},
                    "ltv_cac": {"market": market_case["unit_economics"]["ltv_cac"], "if_founder_right": alt["unit_economics"]["ltv_cac"]},
                    "payback_months": {"market": market_case["unit_economics"]["payback_months"], "if_founder_right": alt["unit_economics"]["payback_months"]}})
    if "monthly_budget" in p["dom"] and {"monthly_budget", "new_customers_per_month"} <= {o["domain"] for o in out}:
        v = dict(base_v); v["monthly_budget"] = p["dom"]["monthly_budget"]["founder"]; v["new_customers_per_month"] = p["dom"]["new_customers_per_month"]["founder"]
        alt = simulate(p, v, "market"); dl = lambda a, b: None if a is None or b is None else round(a - b, 2)
        out.append({"domain": "monthly_budget+new_customers_per_month", "label": "acquisition budget and new customers together (both set the derived CAC)", "kind": "joint",
                    "market": None, "founder": None, "status": "joint", "source": "",
                    "peak_capital_need": {"market": market_case["peak_capital_need"], "if_founder_right": alt["peak_capital_need"], "delta": dl(alt["peak_capital_need"], market_case["peak_capital_need"])},
                    "breakeven_month": {"market": market_case["breakeven_month"], "if_founder_right": alt["breakeven_month"]},
                    "revenue_end": {"month": p["months"], "market": market_case["milestones"]["end"]["mrr"], "if_founder_right": alt["milestones"]["end"]["mrr"], "delta": dl(alt["milestones"]["end"]["mrr"], market_case["milestones"]["end"]["mrr"])},
                    "ltv_cac": {"market": market_case["unit_economics"]["ltv_cac"], "if_founder_right": alt["unit_economics"]["ltv_cac"]},
                    "payback_months": {"market": market_case["unit_economics"]["payback_months"], "if_founder_right": alt["unit_economics"]["payback_months"]}})
    out.sort(key=lambda r: (-abs(r["peak_capital_need"]["delta"] or 0), -abs(r["revenue_end"]["delta"] or 0)))
    return out


def bridge_to_market(p: dict, measured_case: dict) -> list:
    """Measured mode (any founder number is `observed`): from the MEASURED case, move ONE domain to the market mid —
    what reaching the category level on that metric is worth. Base = the measured case."""
    base_v = case_values(p, "founder"); out = []
    for d, s in p["dom"].items():
        if s["fill"] or s["founder"] == s["market"]: continue
        v = dict(base_v); v[d] = s["market"]
        alt = simulate(p, v, "founder")
        dl = lambda a, b: None if a is None or b is None else round(a - b, 2)
        out.append({"domain": d, "label": s["label"], "kind": s["kind"], "measured": s["founder"], "category": s["market"], "status": s["status"], "source": s["source"],
                    "peak_capital_need": {"measured": measured_case["peak_capital_need"], "if_at_category": alt["peak_capital_need"], "delta": dl(alt["peak_capital_need"], measured_case["peak_capital_need"])},
                    "breakeven_month": {"measured": measured_case["breakeven_month"], "if_at_category": alt["breakeven_month"]},
                    "revenue_end": {"month": p["months"], "measured": measured_case["milestones"]["end"]["mrr"], "if_at_category": alt["milestones"]["end"]["mrr"], "delta": dl(alt["milestones"]["end"]["mrr"], measured_case["milestones"]["end"]["mrr"])},
                    "ltv_cac": {"measured": measured_case["unit_economics"]["ltv_cac"], "if_at_category": alt["unit_economics"]["ltv_cac"]},
                    "payback_months": {"measured": measured_case["unit_economics"]["payback_months"], "if_at_category": alt["unit_economics"]["payback_months"]}})
    out.sort(key=lambda r: (-abs(r["revenue_end"]["delta"] or 0), -abs(r["peak_capital_need"]["delta"] or 0)))   # for a live business revenue is the lever that matters
    return out


def tornado(p: dict, market_case: dict) -> list:
    """One domain at a time set to its market LOW and HIGH edge (everything else at the market mid): the width of each bar says how much
    the outcome depends on that assumption — for every row, whether or not the founder gave a number. Rows with a point market value have zero width."""
    base = case_values(p, "market"); out = []
    for d, s in p["dom"].items():
        if s["market_low"] == s["market_high"]: continue
        res = {}
        for edge, v in (("low", s["market_low"]), ("high", s["market_high"])):
            alt = simulate(p, dict(base, **{d: v}), "market")
            res[edge] = {"value": v, "peak_capital_need": alt["peak_capital_need"], "breakeven_month": alt["breakeven_month"], "revenue_end": alt["projection"][-1]["mrr"]}
        width_cap = abs(res["high"]["peak_capital_need"] - res["low"]["peak_capital_need"]); width_rev = abs(res["high"]["revenue_end"] - res["low"]["revenue_end"])
        out.append({"domain": d, "label": s["label"], "kind": s["kind"], "market": s["market"], "low": res["low"], "high": res["high"],
                    "width_capital": round(width_cap, 0), "width_revenue": round(width_rev, 0), "fill": s["fill"]})
    out.sort(key=lambda r: (-r["width_capital"], -r["width_revenue"]))
    return out


def counts(p: dict) -> dict:
    c = {"observed": 0, "founder_stated": 0, "founder_guess": 0, "unverified": 0, "filled_from_market": 0, "total": len(p["dom"])}
    for s in p["dom"].values():
        if s["status"] in c: c[s["status"]] += 1
        if s["fill"] in ("unverified", "filled_from_market"): c[s["fill"]] += 1
    return c


CURRENCY_CODES = {"€": "EUR", "EUR": "EUR", "$": "USD", "USD": "USD", "£": "GBP", "GBP": "GBP", "₽": "RUB", "RUB": "RUB", "CHF": "CHF"}


def capital_vs_round(path, capital: float, currency: str | None = None, fx: dict | None = None):
    """Market-case capital need against a VERIFIED typical-round entry in the model's currency.
    Returns position ∈ below_round | inside_round | above_round, or 'unavailable' with a reason (unverified benchmark,
    unknown currency, no conversion rate). Size only — never a statement that the round can be raised."""
    if not path: return None
    if path not in FUNDING_PATHS: raise ValueError(f"funding_path must be one of {sorted(FUNDING_PATHS)}, got {path!r}")
    code = CURRENCY_CODES.get(str(currency or "").strip().upper()) or CURRENCY_CODES.get(str(currency or "").strip())
    if not code: return {"path": path, "position": "unavailable", "reason": "model currency not given or unknown (set top-level 'currency': EUR / USD / GBP / …)", "capital_need": capital}
    lib = library()
    cands = [e for e in lib.values() if e.get("domain") == "typical_round" and (e.get("applies") or {}).get("stage") == path and e.get("verified") is True]
    if not cands:
        return {"path": path, "position": "unavailable", "reason": f"no verified typical-round benchmark for {path} in the library (unverified: {[i for i in lib if i.startswith('round.') and (lib[i].get('applies') or {}).get('stage') == path]})", "capital_need": capital}
    tier_rank = {"primary": 0, "survey": 1, "secondary": 2, "derived": 3, "method": 3}
    cands.sort(key=lambda e: (tier_rank.get(e.get("tier"), 9), -int(str(e.get("date") or "0")[:4] or 0)))   # newest highest-tier entry wins (library rule)
    same = [e for e in cands if e.get("currency") == code]
    e = same[0] if same else cands[0]
    lo, hi = e["value"]; rate = 1.0; converted = False
    if e.get("currency") != code:
        key = f"{e.get('currency')}_per_{code}"
        rate = (fx or {}).get(key)
        if rate is None or rate == 0: return {"path": path, "position": "unavailable", "reason": f"benchmark {e['id']} is in {e.get('currency')}, the model in {code}; give fx_rates.{key}", "entry": e["id"], "capital_need": capital}
        rate = _num(rate, f"fx_rates.{key}")
        if rate <= 0: raise ValueError(f"fx_rates.{key} must be a positive number")
        converted = True
    cap_in_entry_ccy = capital * rate
    pos = "below_round" if cap_in_entry_ccy < lo else ("above_round" if cap_in_entry_ccy > hi else "inside_round")
    return {"path": path, "round_low": lo, "round_high": hi, "round_currency": e.get("currency"), "model_currency": code, "fx_rate": rate if converted else None,
            "round_low_model_ccy": round(lo / rate, 0), "round_high_model_ccy": round(hi / rate, 0),   # the bounds in the model's own currency — what the report prints
            "is_definition": e.get("tier") in ("derived", "method"),   # bootstrap ceiling is this method's definition, not a market figure
            "capital_need": capital, "capital_in_round_currency": round(cap_in_entry_ccy, 0), "position": pos, "entry": e["id"], "source": e.get("source"), "url": e.get("url"), "date": e.get("date")}


def capital_vs_cash(capital: float, cash: float | None, cash_out_month):
    """Market-case capital need against the money the founder actually has — the comparison that matters when cash_on_hand is given."""
    if cash is None: return None
    gap = round(capital - cash, 0)
    return {"cash_on_hand": cash, "capital_need": capital, "gap": gap, "position": "enough" if gap <= 0 else "short", "cash_out_month": cash_out_month}


def _check_breakdown(case: dict, tag: str, probs: list):
    b = case.get("capital_breakdown")
    if not b: return
    recon = b["upfront"] + b["payroll"] + b["marketing"] + b["fixed"] - b["gross_profit_offset"]
    if case["peak_capital_need"] > 0 and abs(recon - case["peak_capital_need"]) > max(2.0, 0.002 * case["peak_capital_need"]):
        probs.append(f"{tag}: capital breakdown {recon:.0f} does not reconcile with peak capital need {case['peak_capital_need']:.0f}")


def consistency(res: dict) -> list:
    """Cross-checks that comparison, cases and bridge describe the same numbers. Returns a list of problems (empty = consistent)."""
    probs = []
    cmp_ = {c["domain"]: c for c in res["comparison"]}; F, M = res["cases"]["founder"]["inputs"], res["cases"]["market"]["inputs"]
    pairs = [("cac", "blended_cac"), ("monthly_budget", "monthly_budget"), ("gross_margin", "gross_margin_pct"), ("monthly_churn", "monthly_churn_pct"), ("expansion", "expansion_pct"),
             ("repeat_rate", "repeat_rate_pct"), ("new_customers_per_month", "new_customers_per_month_full"), ("fte_cost", "fte_cost"), ("pricing", "price" if res["revenue_unit"] == "one_off" else "arpu0"),
             ("project_value", "project_value"), ("projects_per_year", "projects_per_year"), ("gmv_per_customer_month", "gmv_per_customer_month"), ("take_rate", "take_rate_pct")]
    for d, key in pairs:
        if d not in cmp_ or key not in F: continue
        if d == "cac" and "monthly_budget" in cmp_: continue
        for case, inp in (("founder", F), ("market", M)):
            if abs(inp[key] - cmp_[d][case]) > 0.01 * max(1.0, abs(cmp_[d][case])):
                probs.append(f"{d}: comparison.{case}={cmp_[d][case]} but cases.{case}.inputs.{key}={inp[key]}")
    for b in res["bridge"]:
        if b["kind"] == "joint": continue
        c = cmp_[b["domain"]]
        if b["market"] != c["market"] or b["founder"] != c["founder"]: probs.append(f"bridge {b['domain']}: values differ from comparison")
        if b["peak_capital_need"]["market"] != res["cases"]["market"]["peak_capital_need"]: probs.append(f"bridge {b['domain']}: base is not the market case")
    for c in CASES: _check_breakdown(res["cases"][c], f"cases.{c}", probs)
    return probs


def run_line(cfg: dict) -> dict:
    p = validate(cfg)
    cases = {c: simulate(p, case_values(p, c), c) for c in CASES}
    br = bridge(p, cases["market"])
    observed = {k for k, d in p["dom"].items() if d["status"] == "observed"}
    live = bool(p["start_customers"] or p["start_mrr"]) or p["unit"] == "one_off"
    mode = "measured" if observed and live and (observed & {"monthly_churn", "new_customers_per_month", "repeat_rate", "cac", "monthly_budget"}) else "pre_revenue"
    if observed and mode != "measured":
        p["warnings"].append("some numbers are marked observed but the business has no starting base and no measured churn / volume — the report reads them as the team's numbers, not as a measured business")
    btm = bridge_to_market(p, cases["founder"]) if mode == "measured" else []
    c = counts(p); c["mode"] = mode
    c["category_estimate"] = c["filled_from_market"] * 2 >= c["total"]     # half or more of the rows carry no founder number: this is a category, not a case
    c["starting_base"] = bool(p["start_customers"] or p["start_mrr"])
    tor = tornado(p, cases["market"])
    res = {"cases": cases, "comparison": comparison(p), "bridge": br, "bridge_by_domain": {b["domain"]: b for b in br},
           "tornado": tor, "tornado_by_domain": {t["domain"]: t for t in tor}, "warnings": p["warnings"],
           "mode": mode, "bridge_to_market": btm, "bridge_to_market_by_domain": {b["domain"]: b for b in btm},
           "months": p["months"], "revenue_unit": p["unit"], "name": p["name"], "unit_of_sale": p["unit_of_sale"], "counts": c}
    probs = consistency(res)
    if probs: raise AssertionError("internal inconsistency: " + "; ".join(probs))
    return res


def run_all(cfg: dict) -> dict:
    if "lines" not in cfg:
        res = run_line(cfg)
        res["capital_vs_round"] = capital_vs_round(cfg.get("funding_path"), res["cases"]["market"]["peak_capital_need"], cfg.get("currency"), cfg.get("fx_rates"))
        res["capital_vs_cash"] = capital_vs_cash(res["cases"]["market"]["peak_capital_need"], res["cases"]["market"].get("cash_on_hand"), res["cases"]["market"].get("cash_out_month"))
        if res["capital_vs_round"] is None: raise ValueError("funding_path is required (bootstrap / pre_seed / seed / series_a)")
        return res
    shared = _num(cfg.get("shared_fixed_monthly", 0), "shared_fixed_monthly")
    if shared < 0: raise ValueError("shared_fixed_monthly cannot be negative")
    if not isinstance(cfg["lines"], list) or not cfg["lines"]: raise ValueError("lines must be a non-empty list")
    lines = {}; horizons = {}
    for i, ln in enumerate(cfg["lines"]):
        name = str(ln.get("name", f"line{i+1}"))
        if name.lower() in {n.lower() for n in lines}:
            raise ValueError(f"duplicate line name {name!r} (names are compared case-insensitively — Excel sheet names are)")
        lines[name] = run_line(dict(ln, name=name, _currency=cfg.get("currency"))); horizons[name] = lines[name]["months"]
    if len(set(horizons.values())) != 1:
        raise ValueError(f"all revenue lines must share the same horizon (months); got {horizons}")
    months = next(iter(horizons.values()))
    combined = {}
    for c in CASES:
        rev = [sum(lines[n]["cases"][c]["projection"][m]["mrr"] for n in lines) for m in range(months)]
        cust = [sum(lines[n]["cases"][c]["projection"][m]["customers"] for n in lines) for m in range(months)]
        cum = [sum(lines[n]["cases"][c]["projection"][m]["cumulative"] for n in lines) - shared * (m + 1) for m in range(months)]
        net = [cum[0]] + [cum[m] - cum[m - 1] for m in range(1, months)]
        upfront_total = sum(lines[n]["cases"][c]["inputs"]["upfront_investment"] for n in lines)
        net[0] += upfront_total
        mn = min([-upfront_total] + cum)
        be = None
        for m_ in range(months, 0, -1):
            if net[m_ - 1] >= 0: be = m_
            else: break
        years = {f"y{y+1}": round(sum(rev[y*12:(y+1)*12]), 0) for y in range(months // 12)}
        tot = max(sum(rev), 1)
        share = {n: round(sum(lines[n]["cases"][c]["projection"][m]["mrr"] for m in range(months)) / tot * 100, 1) for n in lines}
        comp = lambda k, m: sum(lines[n]["cases"][c]["projection"][m].get(k, 0) for n in lines)
        proj = [{"month": m + 1, "mrr": round(rev[m], 0), "customers": round(cust[m], 1), "gross_profit": round(comp("gross_profit", m), 0), "marketing": round(comp("marketing", m), 0),
                 "payroll": round(comp("payroll", m), 0), "fixed": round(comp("fixed", m) + shared, 0), "net_cash_flow": round(net[m], 0), "cumulative": round(cum[m], 0)} for m in range(months)]
        trough_m = min(range(months), key=lambda i: cum[i]) + 1
        if cum[trough_m - 1] >= -upfront_total: trough_m = 0
        upto = proj[:trough_m]
        breakdown = {"upfront": round(upfront_total, 0), "payroll": round(sum(r["payroll"] for r in upto), 0), "marketing": round(sum(r["marketing"] for r in upto), 0),
                     "fixed": round(sum(r["fixed"] for r in upto), 0), "gross_profit_offset": round(sum(r["gross_profit"] for r in upto), 0), "trough_month": trough_m,
                     "truncated": trough_m == months and net[-1] < 0}
        flags = [{"id": "no_breakeven", "level": "red"}] if be is None else ([{"id": "strong_economics", "level": "green"}] if be <= 12 else [])
        cash_rec = next((m_ + 1 for m_ in range(months) if m_ + 1 > trough_m and cum[m_] >= 0), None) if trough_m else (1 if cum[0] >= 0 else None)
        combined[c] = {"units_note": "units summed across lines without deduplication", "upfront_investment_total": upfront_total, "cash_recovery_month": cash_rec,
                       "revenue_by_year": years, "breakeven_month": be, "peak_capital_need": round(max(upfront_total, -mn, 0.0), 0), "capital_breakdown": breakdown, "flags": flags,
                       "cumulative_m_last": round(cum[-1], 0), "line_share_pct": share, "projection": proj}
    # combined bridge: each line's bridge row re-evaluated on COMBINED capital need (other lines at market, shared overhead included)
    def comb_peak(projs):
        cum = [sum(pr[m]["cumulative"] for pr in projs) - shared * (m + 1) for m in range(months)]
        up = sum(lines[n]["cases"]["market"]["inputs"]["upfront_investment"] for n in lines)
        return round(max(up, -min([-up] + cum), 0.0), 0), next((i + 1 for i, x in enumerate([cum[0] + up] + [cum[m] - cum[m - 1] for m in range(1, months)]) if x >= 0), None)
    cb = []
    for name, ln in zip(lines, cfg["lines"]):
        p = validate(dict(ln, name=name)); base_v = case_values(p, "market")
        others = [lines[o]["cases"]["market"]["projection"] for o in lines if o != name]
        for b in lines[name]["bridge"]:
            v = dict(base_v)
            if b["kind"] == "joint":
                v["monthly_budget"] = p["dom"]["monthly_budget"]["founder"]; v["new_customers_per_month"] = p["dom"]["new_customers_per_month"]["founder"]
            else:
                v[b["domain"]] = b["founder"]
            alt = simulate(p, v, "market")
            pk, be = comb_peak(others + [alt["projection"]])
            cb.append({"line": name, "domain": b["domain"], "label": b["label"], "kind": b["kind"], "market": b["market"], "founder": b["founder"],
                       "peak_capital_need": {"market": combined["market"]["peak_capital_need"], "if_founder_right": pk, "delta": round(pk - combined["market"]["peak_capital_need"], 2)},
                       "breakeven_month": {"market": combined["market"]["breakeven_month"], "if_founder_right": be}})
    cb.sort(key=lambda r: -abs(r["peak_capital_need"]["delta"]))
    combined["bridge"] = cb
    combined["bridge_by_domain"] = {}
    for x in cb: combined["bridge_by_domain"].setdefault(x["line"], {})[x["domain"]] = x
    tot = {"observed": 0, "founder_stated": 0, "founder_guess": 0, "unverified": 0, "filled_from_market": 0, "total": 0}
    for ln in lines.values():
        for k in tot: tot[k] += ln["counts"][k]
    mode = "measured" if any(ln["mode"] == "measured" for ln in lines.values()) else "pre_revenue"
    tot["mode"] = mode; tot["category_estimate"] = tot["filled_from_market"] * 2 >= tot["total"]; tot["starting_base"] = any(ln["counts"]["starting_base"] for ln in lines.values())
    ctm = []
    if mode == "measured":
        def comb_peak_f(projs):
            cum = [sum(pr[m]["cumulative"] for pr in projs) - shared * (m + 1) for m in range(months)]
            up = sum(lines[n]["cases"]["founder"]["inputs"]["upfront_investment"] for n in lines)
            return round(max(up, -min([-up] + cum), 0.0), 0), next((i + 1 for i, x in enumerate([cum[0] + up] + [cum[m] - cum[m - 1] for m in range(1, months)]) if x >= 0), None), round(sum(pr[-1]["mrr"] for pr in projs), 0)
        for name, ln in zip(lines, cfg["lines"]):
            p = validate(dict(ln, name=name)); base_v = case_values(p, "founder")
            others = [lines[o]["cases"]["founder"]["projection"] for o in lines if o != name]
            for b in lines[name]["bridge_to_market"]:
                v = dict(base_v); v[b["domain"]] = b["category"]
                alt = simulate(p, v, "founder"); pk, be, rv = comb_peak_f(others + [alt["projection"]])
                ctm.append({"line": name, "domain": b["domain"], "label": b["label"], "kind": b["kind"], "measured": b["measured"], "category": b["category"],
                            "peak_capital_need": {"measured": combined["founder"]["peak_capital_need"], "if_at_category": pk, "delta": round(pk - combined["founder"]["peak_capital_need"], 2)},
                            "breakeven_month": {"measured": combined["founder"]["breakeven_month"], "if_at_category": be},
                            "revenue_end": {"month": months, "measured": combined["founder"]["projection"][-1]["mrr"], "if_at_category": rv, "delta": round(rv - combined["founder"]["projection"][-1]["mrr"], 2)}})
        ctm.sort(key=lambda r: (-abs(r["revenue_end"]["delta"] or 0), -abs(r["peak_capital_need"]["delta"] or 0)))
    combined["bridge_to_market"] = ctm
    combined["bridge_to_market_by_domain"] = {}
    for x in ctm: combined["bridge_to_market_by_domain"].setdefault(x["line"], {})[x["domain"]] = x
    cvr = capital_vs_round(cfg.get("funding_path"), combined["market"]["peak_capital_need"], cfg.get("currency"), cfg.get("fx_rates"))
    if cvr is None: raise ValueError("funding_path is required (bootstrap / pre_seed / seed / series_a)")
    return {"lines": lines, "combined": combined, "months": months, "counts": tot, "mode": mode, "capital_vs_round": cvr, "shared_fixed_monthly": shared}


# ── markdown ─────────────────────────────────────────────────

def fmt_money(x) -> str:
    if x is None: return "—"
    return f"{x:,.2f}" if abs(x) < 10 else f"{x:,.0f}"


def line_markdown(res: dict) -> str:
    C = res["cases"]; L = []
    be = lambda x: f"M{x['breakeven_month']}" if x["breakeven_month"] else "not within horizon"
    pb = lambda x: x["unit_economics"]["payback_months"] or "none (60 mo)"
    c = res["counts"]
    L.append(f"### {'Measured vs category' if res['mode'] == 'measured' else 'Founder case vs market case'}  (unit: {res['revenue_unit']}; CAC via {C['market']['inputs']['cac_method']})\n")
    if c.get("category_estimate"): L.append(f"> **Category estimate, not a case:** {c['filled_from_market']} of {c['total']} rows have no founder number and run on the market value.\n")
    if not c.get("starting_base"): L.append("> Starting base: not given — the projection starts from zero customers (for a live business give starting_customers / starting_mrr).\n")
    L.append("| Assumption | Founder (status) | Market (source) | Gap |"); L.append("|---|---|---|---|")
    for r in res["comparison"]:
        mk = f"{r['market']:g}" + (f" [{r['market_low']:g}–{r['market_high']:g}]" if r["market_low"] != r["market_high"] else "")
        L.append(f"| {r['label']} | {r['founder']:g} ({r['status']}{', ' + r['fill'] if r['fill'] else ''}) | {mk} ({r['source'] or 'unverified'}) | {r['gap_ratio'] if r['gap_ratio'] is not None else '—'} |")
    L.append("\n| Outcome | Founder | Market | Pessimistic | Optimistic |"); L.append("|---|---|---|---|---|")
    L.append("| LTV / CAC (cash) | " + " | ".join((f"{C[c]['unit_economics']['ltv_cac']}×" if C[c]["unit_economics"]["ltv_cac"] is not None else "n/a (no cash CAC)") for c in CASES) + " |")
    L.append("| Payback (months) | " + " | ".join(str(pb(C[c])) for c in CASES) + " |")
    L.append("| Break-even | " + " | ".join(be(C[c]) for c in CASES) + " |")
    L.append("| Peak capital need | " + " | ".join(fmt_money(C[c]["peak_capital_need"]) for c in CASES) + " |")
    L.append(f"| Revenue M{res['months']} | " + " | ".join(fmt_money(C[c]["milestones"]["end"]["mrr"]) for c in CASES) + " |")
    if res["bridge"]:
        L.append("\n### Bridge — market case, one assumption at the founder's number\n")
        L.append(f"| Assumption | Market → founder | Peak capital | Break-even | Revenue M{res['months']} | LTV/CAC |"); L.append("|---|---|---|---|---|---|")
        for b in res["bridge"]:
            mv = "—" if b["kind"] == "joint" else f"{b['market']:g} → {b['founder']:g}"
            lc = lambda v: f"{v}×" if v is not None else "n/a"
            L.append(f"| {b['label']} | {mv} | {fmt_money(b['peak_capital_need']['market'])} → {fmt_money(b['peak_capital_need']['if_founder_right'])} | "
                     f"{b['breakeven_month']['market'] or 'none'} → {b['breakeven_month']['if_founder_right'] or 'none'} | {fmt_money(b['revenue_end']['market'])} → {fmt_money(b['revenue_end']['if_founder_right'])} | "
                     f"{lc(b['ltv_cac']['market'])} → {lc(b['ltv_cac']['if_founder_right'])} |")
    if res.get("bridge_to_market"):
        L.append("\n### Where you stand — measured case, one metric brought to the category level\n")
        L.append(f"| Metric | Measured → category | Revenue M{res['months']} | Peak capital | Break-even | LTV/CAC |"); L.append("|---|---|---|---|---|---|")
        lc = lambda v: f"{v}×" if v is not None else "n/a"
        for b in res["bridge_to_market"]:
            L.append(f"| {b['label']} | {b['measured']:g} → {b['category']:g} | {fmt_money(b['revenue_end']['measured'])} → {fmt_money(b['revenue_end']['if_at_category'])} | {fmt_money(b['peak_capital_need']['measured'])} → {fmt_money(b['peak_capital_need']['if_at_category'])} | "
                     f"{b['breakeven_month']['measured'] or 'none'} → {b['breakeven_month']['if_at_category'] or 'none'} | {lc(b['ltv_cac']['measured'])} → {lc(b['ltv_cac']['if_at_category'])} |")
    if C["market"].get("warnings"): L.append("\n**Warnings:** " + " · ".join(C["market"]["warnings"]))
    return "\n".join(L)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cfg = json.load(open(sys.argv[1]))
    res = run_all(cfg)
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2)); return
    if "lines" in res:
        for n, r in res["lines"].items(): print(f"\n## Line: {n}\n"); print(line_markdown(r))
        c = res["combined"]
        print("\n## Combined (all lines)\n"); print("| | Founder | Market | Pessimistic | Optimistic |"); print("|---|---|---|---|---|")
        for y in c["market"]["revenue_by_year"]:
            print(f"| Revenue {y.upper()} | " + " | ".join(fmt_money(c[k]["revenue_by_year"][y]) for k in CASES) + " |")
        print("| Break-even | " + " | ".join(f"M{c[k]['breakeven_month']}" if c[k]["breakeven_month"] else "none" for k in CASES) + " |")
        print("| Peak capital need | " + " | ".join(fmt_money(c[k]["peak_capital_need"]) for k in CASES) + " |")
        return
    print(line_markdown(res))


if __name__ == "__main__":
    main()
