#!/usr/bin/env python3
"""
Render the viability report from report.json + model.json — the team's case vs the market's case.

Usage:
    python build_report.py report.json charts_dir out.html --model model.json [--strict]   # interactive page (one self-contained file)
    python build_report.py report.json charts_dir out.pdf  --model model.json [--strict]   # print of the same content, paginated and verified
    python build_report.py report.json charts_dir out.docx --model model.json [--strict]   # Word, if someone needs it

What the builder guarantees
  • Every numeric exhibit is GENERATED from model.json: KPI tiles, the team-vs-market comparison with range bars, the bridge and
    the tornado, the financial picture (P&L, cumulative cash, capital waterfall, threshold check), unit economics, outcomes,
    the funnel, the comparable benchmark, the assumptions pack.
  • Every number in prose is either a {{ref|fmt}} placeholder rendered from the model — bound to a field and a case — or declared
    in manual_numbers {value, field, source, where, context}. `context` is a phrase that appears VERBATIM in the text at one of
    the `where` paths and contains the number; a declaration covers one meaning. Skipped: dates, bare 4-digit years, bare
    integers below 10, digits inside URLs, the row-number column of appendix tables, a token that is digits glued to a word
    (2pr.io). "300k", "1.5M", "5 тыс." are numbers in that form. `python number_audit.py report.json model.json` lists what is missing.
  • Charts must carry manifests (charts.json, dashboard.json) written by build_workbook / build_dashboard from the SAME model.json.
  • Required content: a verdict from four with its rule (a category estimate must be "Not assessable"); `conditions` for
    "Proceed with conditions" / "Not assessable"; exactly five story sentences; a story (belief / evidence / stakes / test) for each of the
    top-3 bridge rows (team cost excluded); a lead + paragraphs for the market case, the team case and the competition; a competitive
    table (2–3 dimensions, ≥ 5 rows incl. the startup); 3–5 next-90-days items with a test for the top bridge row, every `unverified`
    row and the widest filled-from-market tornado row; ≥ 2 risks with what / impact / signal / action; the evidence pack.
  • Page 1 = title · verdict (+ conditions, optional kill criterion) · five sentences · where the numbers come from · KPI tiles ·
    comparison (≤ page1_rows rows, default 5, ranked by the bridge; filled-from-market rows as a compact strip). Page 2 = financial
    picture (landscape). Page 3 opens with the assumptions. Budget: verdict_text ≤ 320 chars raw (≤ 480 rendered — the funding-path
    placeholder expands to a sentence), story ≤ 900 rendered, evidence_basis ≤ 180. After the build the PDF pagination is verified;
    on failure the file is kept as <name>.FAILED.pdf for inspection and the build exits non-zero.
  • Register lint (second person, author voice, chat connectors, informal evaluation) warns; --strict fails.

report.json — a narrative, not a form. Every section is prose the author writes; the builder adds the exhibits.
{
  "startup", "date", "lang": "en"|"ru", "currency": "€", "line": "Placement" (multi-line only: the leading line),
  "verdict": "Proceed" | "Proceed with conditions" | "Rethink" | "Not assessable",
  "verdict_text": "≤ 320 chars; must contain {{capital_vs_round.position|text}}",
  "conditions": ["2–4 lines with a number or placeholder"],            # required for Proceed with conditions / Not assessable
  "kill_criterion": {"metric": "…", "threshold": "…", "what_model_shows": "…"},   # optional; page 1
  "story": ["…", "…", "…", "…", "…"],                                 # exactly five sentences; plain language
  "evidence_basis": "placeholders into counts.*",
  "page1_rows": 5,                                                     # optional, 3–5: how many comparison rows page 1 carries
  "assumptions": {"lead": "…", "stories": [{"domain": "…", "line": "…" (multi-line), "belief": "…", "evidence": "…",
                  "stakes": "placeholders into bridge_by_domain.<domain>.* (or combined.bridge_by_domain.<line>.<domain>.*)", "test": "…"}]},
  "market_case": {"lead": "…", "paragraphs": ["…"]},
  "founder_case": {"lead": "…", "paragraphs": ["…"]},
  "competition": {"lead": "…", "dimensions": [{"key": "…", "label": "…", "why": "…"}, …2–3],
                  "rows": [{"name": "…", "layer": "direct|indirect|displacer", "price": "…", "cells": {"<key>": "…"}, "source": "…", "self": false}, …≥5],
                  "paragraphs": ["…"], "where_we_win": "…"},
  "next_90_days": [{"domain": "<assumption or other>", "title": "…", "what": "…", "how": "…", "threshold": "…"}],   # 3–5
  "risks": [{"title": "…", "likelihood": "High|Medium|Low", "reversibility": "Reversible|Structural|Unknown", "what": "…", "impact": "…", "signal": "…", "action": "…"}],
  "appendix": {"evidence": [[hdr], …]},
  "manual_numbers": [{"value": "…", "field": "…", "source": "…", "where": ["path"], "context": "phrase with the number"}],
  "labels": {overrides, same keys and shapes as LABELS[lang]}
}
"""

import json
import os
import re
import sys

import chart_style
from chart_style import fmt_money, fmt_mult, fmt_pct

try:   # python-docx is only needed for .docx output; HTML and PDF work without it
    from docx import Document
    from docx.enum.section import WD_ORIENT, WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    HAVE_DOCX = True
except ImportError:   # pragma: no cover
    HAVE_DOCX = False
    class RGBColor:   # colour constants below are built at import time
        def __init__(self, *a): pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from financial_model import CASES  # noqa: E402

NAVY = RGBColor(0x1F, 0x38, 0x64); GREY = RGBColor(0x59, 0x59, 0x59)
VERDICTS = ("Proceed", "Proceed with conditions", "Rethink", "Not assessable")
VERDICT_COLORS = {"Proceed": "27AE60", "Proceed with conditions": "E67E22", "Rethink": "C0392B", "Not assessable": "6B7280"}
PAGE1_LIMITS = {"verdict_text": 320, "evidence_basis": 180}
STORY_LIMIT = 900
PAGE1_ROWS = 5
TOP_STORIES = 3
COST_DOMAINS = {"fte_cost"}   # what the team pays itself is a plan input, not a disagreement with the market: never a required story, ranked last on page 1
FORMATS = ("money", "mult", "months", "month", "pct", "int", "text")
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.\- ]+?)\s*(?:\|\s*([A-Za-z]+)\s*)?\}\}")
ANY_BRACES = re.compile(r"\{\{|\}\}")
IDENTITY_KEYS = {"manual_numbers", "lang", "currency", "line", "date", "ref", "fmt", "pair", "domain", "where", "likelihood", "reversibility", "layer", "self", "key", "dimensions_keys"}
NO_PLACEHOLDER_KEYS = {"labels", "startup"}
CASE_LABEL_KEYS = {"founder": "founder", "market": "market", "pessimistic": "pessimistic", "optimistic": "optimistic"}

LABELS = {
    "en": {
        "title_suffix": "Viability Assessment", "scope_note": "Pre-diligence assessment for the founding team. Not investment due diligence.",
        "evidence_basis": "Where the numbers come from", "verdict_k": "Verdict", "verdict_names": {"Proceed": "PROCEED", "Proceed with conditions": "PROCEED WITH CONDITIONS", "Rethink": "RETHINK", "Not assessable": "NOT ASSESSABLE YET"},
        "cond_k": "Conditions", "mfmt": "M{v}", "need_k": "What is needed to assess it", "kill_k": "The team's own kill criterion", "kill_model": "what the model shows",
        "kpi_hint": ["gross profit a customer brings over its life vs the cost of winning it; the usual bar is 3", "months until a customer has earned back its acquisition cost", "the month from which income covers costs for good", "cash the business has to have at the start (deepest point of cumulative cash)", "monthly revenue at the end of the horizon", "the month cumulative cash is back at zero — the outlay earned back"],
        "ue_title": "Economics of one customer", "market_status": {"cited": "named source", "library": "benchmark library", "derived": "analyst's estimate"}, "lib_flag": {"unverified": "library entry not verified", "stale": "library entry older than 24 months"}, "lib_flag_note": "the library entry behind this value is unverified or older than 24 months — a working estimate until research replaces it",
        "glossary_h": "H. Terms used in this report", "glossary": [["LTV", "lifetime value — the gross profit one customer brings over its whole time with the business (capped at 60 months)"], ["CAC", "customer acquisition cost — cash spent to win one new customer; the loaded version adds the selling share of payroll"], ["Gross profit / gross margin", "revenue minus the direct cost of delivering to the customer; the margin is that as a share of revenue"], ["Churn", "the share of customers who leave each month"], ["Break-even", "the month from which income covers all costs for good"], ["Capital need", "the deepest point of cumulative cash — the money that must be there at the start"], ["Cumulative cash", "money on the account month after month, starting from the upfront outlay"], ["Bridge", "the effect of one assumption alone: the team's number instead of the market's, everything else unchanged"], ["Tornado", "the effect of one market assumption alone at its low and high edge — how much the outcome depends on it"], ["Market edges", "every market assumption at its worst (or best) end at once — a boundary, not a likely outcome"], ["Funding path", "how the business is meant to be financed: own funds (bootstrap), pre-seed, seed, Series A"]],
        "comparison": "The team's numbers vs the market's", "bridge": "Which of the team's numbers matter most to prove",
        "story": "In five sentences", "assumptions": "What the team believes and what the market shows", "market_case": "The business on the market's numbers",
        "founder_case": "If the team is right", "competition": "The competitive picture", "next_90": "The next 90 days", "risks_h": "Risks",
        "st_believes": "The team assumes", "st_evidence": "What the market shows", "st_stakes": "What it is worth", "st_test": "How to find out",
        "vs": "{f} (team) vs {m} (market)", "layer_direct": "Solving the same problem directly", "layer_indirect": "By other routes", "layer_displacers": "Could make the product unnecessary",
        "dims_intro": "What defines a product in this segment", "col_product": "Product", "col_layer": "Layer", "col_price": "Price / month", "col_source": "Source", "self_mark": "this report",
        "layer_short": {"direct": "direct", "indirect": "other route", "displacer": "displacer"}, "risk_enum": {"High": "High", "Medium": "Medium", "Low": "Low", "Reversible": "Reversible", "Structural": "Structural", "Unknown": "Unknown"},
        "col_what_happens": "What happens to the numbers", "col_signal": "Early signal", "risks_intro": "A risk is an event outside the assumption ranges or a structural threat; unproven assumptions are tested in the next 90 days, not listed here.",
        "why_bridge": "Why this comes first: capital need {a} → {b} if the team is right.", "ap_assumptions": "A. Assumptions pack", "ap_evidence": "B. Evidence pack",
        "ap_cases": "C. Four cases in detail", "ap_ue": "D. Unit economics", "ap_funnel": "E. Funnel and growth", "ap_comparable": "F. Comparable benchmark", "ap_bridge": "G. Bridge — every assumption", "ap_bridge_comb": "Combined effect across all lines (shared overhead included) — this is what ranks the report",
        "market_range": "Extreme scenarios: every market assumption at its worst or best end", "no_cash_cac": "∞ (no cash cost to acquire)", "ue_cac_loaded": "CAC incl. selling payroll", "ue_ltvcac_loaded": "LTV / CAC incl. selling payroll", "ue_payback_loaded": "Payback incl. selling payroll (months)", "ue_ltvcac_time": "LTV / CAC incl. founder time", "ue_payback_time": "Payback incl. founder time (months)",
        "enum": {"below_round": "below the typical round for this path", "inside_round": "inside the typical round for this path", "above_round": "above the typical round for this path",
                 "above_comparables": "above comparables", "within_range": "within range", "far_below_comparables": "far below comparables", "no_reference": "no reference",
                 "unavailable": "comparison with a typical round unavailable (no verified benchmark in the model's currency)"},
        "bridge_intro": "Start from the market case and let the team be right about one assumption at a time. The change in capital need ranks the assumptions by how much is riding on each.",
        "bridge_note": "The bars do not add up to the difference between the two cases: assumptions interact (a higher price with the same churn is worth more than either alone). Under a paid motion, budget and customer volume are also shown together because both set the derived cost to acquire.",
        "market_range_note": "The pessimistic and optimistic columns put every market range at its worst or best edge at once — bounds, not a likely band.",
        "dashboard": "Financial picture", "dashboard_note": "All figures on this page are computed by the model from the two cases; the accompanying workbook reproduces them with formulas.",
        "signals": "Strongest signal · Main risk · Most important unknown", "strongest": "Strongest signal", "main_risk": "Main risk", "unknown": "Most important unknown",
        "grounded": "What looks grounded", "weak": "What is weakly supported", "contradictions": "Where things don't add up",
        "competitors": "Competitive landscape", "direct": "Direct competitors", "indirect": "Indirect competitors", "displacers": "Displacers", "where_we_win": "Where this idea can win",
        "unit_economics": "Unit economics", "growth": "How customers arrive: the funnel", "outcomes": "Four cases: founder, market, and the benchmark's edges",
        "comparable": "Comparable benchmark vs bottom-up model", "prove": "What you still need to prove", "risks": "Risks",
        "appendix": "Appendix", "calibration": "A. Calibration pack", "evidence": "B. Evidence pack",
        "model_note": "Full model with editable assumptions: see the accompanying .xlsx file. Method: Startup Viability Check © Maxim Mikhalyov (linkedin.com/in/maximmikhalyov), CC BY-NC 4.0 — non-commercial use with attribution; commercial use by permission.",
        "col_item": "Assumption", "col_range": "Range", "col_basis": "Basis", "col_upgrade": "What would upgrade it",
        "col_name": "Name", "col_price": "Price", "col_note": "Note", "col_threat": "Threat", "col_defence": "Defence",
        "col_test": "Test", "col_how": "How", "col_threshold": "Threshold", "col_risk": "Risk", "col_likelihood": "Likelihood", "col_reversibility": "Reversibility", "col_action": "Action",
        "founder": "Team", "market": "Market", "pessimistic": "All edges worst", "optimistic": "All edges best", "line": "Line", "none": "none", "not_within": "not within {n} mo", "never": "not within 60 mo",
        "cmp_hdr": ["Assumption", "Founder (status)", "Market (source)", "Gap", "If the founder is right (market case otherwise)"],
        "cap_short": "capital", "be_short": "break-even", "rev_short": "revenue",
        "cmp_more": "{n} further assumptions with a smaller effect are listed in the bridge section.", "cmp_rest": "Remaining assumptions",
        "cmp_filled": "No team number — the model runs on the market value",
        "paths": {"bootstrap": "bootstrapping (own funds)", "pre_seed": "a pre-seed round", "seed": "a seed round", "series_a": "a Series A round"}, "upto": "up to {x}",
        "round_text": {"above_round": "{diff} more than is usual for {path} ({rng})", "inside_round": "within what is usual for {path} ({rng})", "below_round": "{diff} less than is usual for {path} ({rng})"},
        "cash_text": {"enough": "the {cash} on hand covers it", "short": "the {cash} on hand falls {gap} short — cash runs out in month {m}"},
        "fin": {"pl_title": "Monthly P&L", "pl_sub": "revenue (bars), gross profit (dashed) and net result (lines) — market case, team's net result overlaid", "rev": "Revenue", "gp": "Gross profit", "net_m": "Net — market", "net_f": "Net — team", "be": "break-even", "m": "M",
                "cash_title": "Cumulative cash", "cash_sub": "the trough is the capital the business needs; the band is the market edges (all worst / all best)", "need": "capital need", "payback_cash": "cash back to zero", "market": "Market", "team": "Team", "edges": "Market edges",
                "cap_title": "Capital need — where the money goes before the cash trough", "cap_sub": "outlays until the deepest point of cumulative cash, minus the gross profit earned by then", "spent": "Outlays", "covered": "Covered by gross profit", "payroll": "Payroll", "marketing": "Acquisition", "fixed": "Other fixed", "upfront": "Upfront", "round": "typical round for the path",
                "flags_title": "Check against the usual thresholds", "f_ltvcac": "LTV / CAC", "f_loaded": "(incl. selling payroll)", "f_payback": "CAC payback", "f_be": "Break-even", "f_capital": "Capital vs typical round", "f_inf": "∞ — no cash cost to acquire", "f_below1": "below 1: each customer loses money", "f_below3": "below 3: thin", "f_never": "not within 60 months", "f_slow": "slower than 18 months", "f_mo": "mo", "f_no_be": "not within {n} months",
                "f_pos": {"below_round": "below the typical round", "inside_round": "inside the typical round", "above_round": "above the typical round"}, "need_x": "Need (trough at M{m})", "upto_x": "up to {x}", "usual_for": "Usual for {path}", "gp_short": "Gross profit earned by then", "paths": {"bootstrap": "bootstrapping", "pre_seed": "pre-seed", "seed": "seed", "series_a": "Series A"},
                "cap_sentence": "Until cumulative cash bottoms out in month {m} the business spends {gross} ({items}) and earns {off} of gross profit in the meantime; the difference, {need}, is the money it has to have at the start.", "cap_round": "That is {text}.",
                "flags_intro": "The market-case numbers of the model checked against the thresholds investors usually apply to early-stage economics — a reading aid, not new facts.", "c_metric": "Metric", "c_rule": "Usual rule", "c_model": "In the model", "c_verdict": "Reading",
                "r_ltvcac": "at least 3 (below 1: each customer loses money)", "r_payback": "no longer than 18 months", "r_be": "within the {n}-month horizon; before M12 is strong", "r_capital": "within what is usual for {path} ({rng})", "verdicts": {"green": "fine", "amber": "thin", "red": "problem"}, "page_title": "Financial picture — the business on the market's numbers", "show": "Show", "bridge_title": "If the team is right about ONE assumption (market case otherwise) — change in capital need", "bridge_title_m": "If ONE metric reached the category level (rest as measured) — change in revenue at the last month", "note_bridge": "bars do not add up: assumptions interact", "t_title": "How much the outcome depends on each market assumption", "t_sub": "one assumption at a time at the low and high end of its market range, everything else at the market mid — capital need", "t_base": "market case", "t_noteam": "no team number", "t_note": "green = less capital needed, red = more", "rev_m": "Monthly revenue", "cum": "Cumulative cash", "cust": "Active customers", "purch": "Purchases per month", "edge_lo": "All edges worst", "edge_hi": "All edges best"}, "cmp_filled_note": "These rows carry no comparison: the first measured number for each replaces the market value.", "if_right": "if the team is right",
        "bridge_hdr": ["Assumption", "Market → founder", "Capital need", "Break-even", "Revenue M{n}", "LTV / CAC", "Payback"],
        "status": {"observed": "measured", "founder_stated": "stated", "founder_guess": "guess", "benchmarked": "no founder number — market value used"},
        "fill": {"unverified": "no market data — founder's number used", "filled_from_market": "", "derived_from_channels": "channel table"},
        "ue_cac": "Blended cost to acquire a customer (CAC)", "ue_arpu": "Revenue per customer-month", "ue_price": "Price per purchase",
        "ue_churn": "Monthly churn", "ue_repeat": "Repeat rate", "ue_margin": "Gross margin",
        "ue_ltv": "Lifetime gross-margin contribution per customer (LTV, 60-month cap)", "ue_ltvcac": "LTV / CAC", "ue_payback": "Payback (months, cumulative)",
        "ue_arpu3": "Revenue per customer-month needed for LTV/CAC = 3",
        "sc_be": "Break-even month", "sc_cap": "Peak capital need", "sc_rev": "Revenue, month {n}", "sc_units": "{u}, month {n}", "sc_year": "Revenue, year {y}",
        "sc_cum": "Cumulative cash, month {n}", "sc_burn": "Monthly fixed burn", "customers": "Customers", "purchases": "Purchases",
        "cb_seg": "Segment size", "cb_pen": "Comparable penetration", "cb_ref": "Reference customers (3 years)", "cb_bu": "Bottom-up customers, month 36", "cb_pos": "Position",
        "pos": {"above_comparables": "above comparables", "within_range": "within range", "far_below_comparables": "far below comparables", "no_reference": "no reference",
                 "unavailable": "comparison with a typical round unavailable (no verified benchmark in the model's currency)"},
        "growth_text": "Motion: {motion} · ramp reaches 50 % of capacity at month {mid} · sales-cycle lag {lag} mo",
        "capacity_text": "New customers per month at full capacity — founder {f} · market {m} (benchmark range {lo}–{hi})",
        "funnel_hdr": ["Step", "Value", "Source"],
        "dom": {"pricing": "price", "project_value": "project value", "projects_per_year": "projects per client per year", "gmv_per_customer_month": "GMV per customer per month",
                "take_rate": "take rate", "gross_margin": "gross margin", "monthly_churn": "monthly churn", "expansion": "expansion", "repeat_rate": "repeat rate",
                "cac": "cost to acquire", "monthly_budget": "acquisition budget", "new_customers_per_month": "new customers per month", "fte_cost": "cost per team member, monthly",
                "monthly_budget+new_customers_per_month": "budget and customers together"},
        "kpi_default": ["LTV / CAC — founder | market", "Payback, months — founder | market", "Break-even, month — founder | market", "Capital need — founder | market",
                        "Revenue, month {n} — founder | market", "Outlay earned back, month — founder | market"],
        "_measured": {"comparison": "Where you stand: measured vs the category", "assumptions": "What each metric is worth at the category level",
                      "bridge_intro": "Start from the business as measured and bring one metric to the category level at a time. The change in revenue and capital need ranks the metrics by what fixing each is worth.",
                      "founder": "Measured", "market": "Category", "founder_case": "The business as measured", "market_case": "The business at category level",
                      "st_believes": "Measured", "st_evidence": "Category benchmark", "st_stakes": "What reaching the category level is worth", "st_test": "How to move it",
                      "vs": "{f} (measured) vs {m} (category)", "cmp_hdr": ["Metric", "Measured (source)", "Category (source)", "Gap", "If this metric reached the category level (rest as measured)"],
                      "kpi_default": ["LTV / CAC — measured | category", "Payback, months — measured | category", "Break-even, month — measured | category", "Capital need — measured | category",
                                      "Revenue, month {n} — measured | category", "Outlay earned back, month — measured | category"]},
    },
    "ru": {
        "title_suffix": "Оценка жизнеспособности", "scope_note": "Предварительная оценка для команды основателей. Не является инвестиционной экспертизой.",
        "evidence_basis": "Откуда цифры", "verdict_k": "Вердикт", "verdict_names": {"Proceed": "ДВИГАТЬСЯ ДАЛЬШЕ", "Proceed with conditions": "ДВИГАТЬСЯ С УСЛОВИЯМИ", "Rethink": "ПЕРЕСМОТРЕТЬ", "Not assessable": "ПОКА НЕ ОЦЕНИТЬ"},
        "cond_k": "Условия", "mfmt": "{v}-й мес.", "need_k": "Что нужно, чтобы оценить", "kill_k": "Kill-критерий команды", "kill_model": "что показывает модель",
        "kpi_hint": ["валовая прибыль с клиента за всё время против затрат на его привлечение; обычный ориентир — не ниже 3", "через сколько месяцев клиент отбивает затраты на своё привлечение", "месяц, с которого доходы покрывают расходы уже насовсем", "деньги, которые нужно иметь на старте (самая низкая точка накопленного кэша)", "месячная выручка в конце горизонта расчёта", "месяц, когда накопленный кэш снова на нуле — вложения возвращены"],
        "ue_title": "Экономика одного клиента", "market_status": {"cited": "названный источник", "library": "библиотека ориентиров", "derived": "оценка аналитика"}, "lib_flag": {"unverified": "запись библиотеки не проверена", "stale": "записи библиотеки больше 24 месяцев"}, "lib_flag_note": "запись библиотеки за этим значением не проверена или старше 24 месяцев — рабочая оценка, пока исследование её не заменит",
        "glossary_h": "H. Термины, которые встречаются в отчёте", "glossary": [["LTV", "пожизненная ценность клиента — валовая прибыль, которую один клиент приносит за всё время работы с ним (в расчёте — не дольше 60 месяцев)"], ["CAC", "стоимость привлечения клиента — деньги, потраченные, чтобы получить одного нового клиента; «с учётом продаж» — плюс доля зарплат, уходящая на продажи"], ["Валовая прибыль / валовая маржа", "выручка минус прямые затраты на выполнение работы для клиента; маржа — та же величина в процентах от выручки"], ["Отток", "доля клиентов, уходящих за месяц"], ["Выход в плюс", "месяц, с которого доходы покрывают все расходы уже насовсем (безубыточность)"], ["Потребность в капитале", "самая низкая точка накопленного кэша — деньги, которые должны быть на старте"], ["Накопленный кэш", "деньги на счёте месяц за месяцем, начиная со стартовых вложений"], ["Мост", "эффект одного допущения: цифра команды вместо рыночной при прочих равных"], ["Торнадо", "эффект одного рыночного допущения на его худшем и лучшем крае — насколько итог зависит от него"], ["Крайние сценарии", "все рыночные допущения сразу на худшем (или лучшем) краю — граница возможного, а не вероятный исход"], ["Путь финансирования", "как бизнес собирается финансироваться: свои средства (bootstrap), pre-seed, seed, Series A"]],
        "comparison": "Где команда расходится с рынком", "bridge": "Какие цифры команды важнее всего доказать",
        "story": "В пяти предложениях", "assumptions": "Что заявляет команда и что показывает рынок", "market_case": "Бизнес по рыночным оценкам",
        "founder_case": "Если верны цифры команды", "competition": "Конкурентное поле", "next_90": "Ближайшие 90 дней", "risks_h": "Риски",
        "st_believes": "Допущение команды", "st_evidence": "Что показывает рынок", "st_stakes": "Сколько это стоит", "st_test": "Как проверить",
        "vs": "цифра команды {f} · рынок {m}", "layer_direct": "Решают ту же задачу напрямую", "layer_indirect": "Обходными путями", "layer_displacers": "Могут сделать продукт ненужным",
        "dims_intro": "Признак", "col_product": "Продукт", "col_layer": "Тип", "col_price": "Цена / мес", "col_source": "Источник", "self_mark": "оцениваемая компания",
        "layer_short": {"direct": "прямой конкурент", "indirect": "решает задачу иначе", "displacer": "может сделать продукт ненужным"}, "risk_enum": {"High": "высокая", "Medium": "средняя", "Low": "низкая", "Reversible": "можно исправить", "Structural": "свойство рынка", "Unknown": "неясно"},
        "col_what_happens": "Как изменится расчёт", "col_signal": "Ранний сигнал", "risks_intro": "Риск — событие за пределами диапазонов допущений или структурная угроза; непроверенные допущения проверяются в «ближайших 90 днях», а не перечисляются здесь.",
        "why_bridge": "Почему это первое: потребность в капитале {a} → {b}, если права команда.", "ap_assumptions": "A. Пакет допущений", "ap_evidence": "B. Пакет доказательств",
        "ap_cases": "C. Четыре сценария подробно", "ap_ue": "D. Юнит-экономика", "ap_funnel": "E. Воронка и рост", "ap_comparable": "F. Ориентир по аналогам", "ap_bridge": "G. Как каждое допущение меняет итог (мост и торнадо)", "ap_bridge_comb": "Совокупный эффект по всем линиям (с общими расходами) — по нему ранжирован отчёт",
        "market_range": "Крайние сценарии: все рыночные допущения на худшем или лучшем краю", "no_cash_cac": "∞ (привлечение без денежных затрат)", "ue_cac_loaded": "Стоимость привлечения с учётом зарплат на продажи", "ue_ltvcac_loaded": "LTV / CAC с учётом зарплат на продажи", "ue_payback_loaded": "Окупаемость с учётом зарплат на продажи (мес)", "ue_ltvcac_time": "LTV / CAC с учётом времени команды", "ue_payback_time": "Окупаемость с учётом времени команды (мес)",
        "enum": {"below_round": "меньше типичного раунда для этого пути", "inside_round": "в пределах типичного раунда для этого пути", "above_round": "больше типичного раунда для этого пути",
                 "above_comparables": "выше аналогов", "within_range": "в диапазоне", "far_below_comparables": "далеко ниже аналогов", "no_reference": "нет ориентира",
                 "unavailable": "сравнение с типичным раундом недоступно (нет проверенного ориентира в валюте модели)"},
        "bridge_intro": "Отправная точка — кейс рынка; команда оказывается права в одном допущении за раз. Изменение потребности в капитале ранжирует допущения по тому, сколько от каждого зависит.",
        "bridge_note": "Столбики не складываются в разницу между двумя сценариями: допущения взаимодействуют (более высокая цена при том же оттоке стоит больше, чем каждое по отдельности). При платном привлечении бюджет и объём клиентов показаны и вместе — оба задают расчётную стоимость привлечения.",
        "market_range_note": "Пессимистичный и оптимистичный столбцы ставят каждое рыночное допущение на худший или лучший край одновременно — это границы возможного, а не вероятный коридор.",
        "dashboard": "Финансовая картина", "dashboard_note": "Все значения на этой странице рассчитаны моделью; прилагаемая книга Excel воспроизводит их формулами.",
        "signals": "Сильнейший сигнал · Главный риск · Главное неизвестное", "strongest": "Сильнейший сигнал", "main_risk": "Главный риск", "unknown": "Главное неизвестное",
        "grounded": "Что выглядит обоснованным", "weak": "Что подтверждено слабо", "contradictions": "Где цифры не сходятся",
        "competitors": "Конкурентное поле", "direct": "Прямые конкуренты", "indirect": "Косвенные конкуренты", "displacers": "Вытеснители", "where_we_win": "Где идея может выиграть",
        "unit_economics": "Юнит-экономика", "growth": "Как приходят клиенты: воронка", "outcomes": "Четыре сценария: команда, рынок, пессимистичный и оптимистичный край",
        "comparable": "Ориентир по аналогам против модели снизу вверх", "prove": "Что ещё предстоит доказать", "risks": "Риски",
        "appendix": "Приложение", "calibration": "A. Калибровочный пакет", "evidence": "B. Пакет доказательств",
        "model_note": "Полная модель с редактируемыми допущениями — в прилагаемом файле .xlsx. Метод: Startup Viability Check © Максим Михалёв (linkedin.com/in/maximmikhalyov), CC BY-NC 4.0 — некоммерческое использование с указанием автора; коммерческое — с разрешения автора.",
        "col_item": "Допущение", "col_range": "Диапазон", "col_basis": "Основание", "col_upgrade": "Что повысит уверенность",
        "col_name": "Название", "col_price": "Цена", "col_note": "Примечание", "col_threat": "Угроза", "col_defence": "Защита",
        "col_test": "Проверка", "col_how": "Как", "col_threshold": "Порог", "col_risk": "Риск", "col_likelihood": "Вероятность", "col_reversibility": "Исправимо ли", "col_action": "Действие",
        "founder": "Команда", "market": "Рынок", "pessimistic": "Пессимистичный", "optimistic": "Оптимистичный", "line": "Линия", "none": "нет", "not_within": "нет за {n} мес", "never": "нет за 60 мес",
        "cmp_hdr": ["Допущение", "Команда (статус)", "Рынок (источник)", "Разрыв", "Если команда права (остальное — по рынку)"],
        "cap_short": "капитал", "be_short": "плюс", "rev_short": "выручка",
        "cmp_more": "Ещё {n} допущений с меньшим эффектом — в приложении G.", "cmp_rest": "Остальные допущения",
        "cmp_filled": "Цифры команды нет — в расчёте взято рыночное значение",
        "paths": {"bootstrap": "bootstrap — свои средства", "pre_seed": "раунд pre-seed", "seed": "раунд seed", "series_a": "раунд Series A"}, "upto": "до {x}",
        "round_text": {"above_round": "на {diff} больше, чем обычно вкладывают при пути «{path}» ({rng})", "inside_round": "в пределах обычного для пути «{path}» ({rng})", "below_round": "на {diff} меньше обычного для пути «{path}» ({rng})"},
        "cash_text": {"enough": "денег на счёте ({cash}) хватает", "short": "денег на счёте ({cash}) не хватает на {gap} — они закончатся в месяце {m}"},
        "fin": {"pl_title": "Доходы и расходы по месяцам", "pl_sub": "выручка столбиками, валовая прибыль пунктиром, чистый результат линиями — по рыночным оценкам; оранжевая линия — чистый результат на цифрах команды", "rev": "Выручка", "gp": "Валовая прибыль", "net_m": "Чистый результат — рынок", "net_f": "Чистый результат — команда", "be": "выход в плюс", "m": "месяц ",
                "cash_title": "Деньги на счёте нарастающим итогом", "cash_sub": "нижняя точка кривой — сколько денег нужно бизнесу; заливка — диапазон от пессимистичного до оптимистичного края рынка", "need": "потребность", "payback_cash": "вложения возвращены", "market": "Рынок", "team": "Команда", "edges": "Диапазон рынка",
                "cap_title": "Потребность в капитале — из чего она складывается", "cap_sub": "расходы до нижней точки накопленного кэша минус валовая прибыль, заработанная к этому моменту", "spent": "Расходы до нижней точки", "covered": "Покрыто валовой прибылью", "payroll": "Зарплаты", "marketing": "Привлечение", "fixed": "Прочие постоянные расходы", "upfront": "Стартовые вложения", "round": "типичный раунд для выбранного пути",
                "flags_title": "Сравнение с общепринятыми ориентирами", "f_ltvcac": "LTV / CAC", "f_loaded": "(с учётом зарплат на продажи)", "f_payback": "Окупаемость CAC", "f_be": "Выход в плюс", "f_capital": "Нужный капитал и обычный объём для пути", "f_inf": "∞ — привлечение без денежных затрат", "f_below1": "ниже 1: каждый клиент убыточен", "f_below3": "ниже 3: запас тонкий", "f_never": "не за 60 месяцев", "f_slow": "дольше 18 месяцев", "f_mo": "мес", "f_no_be": "нет за {n} месяцев",
                "f_pos": {"below_round": "меньше типичного раунда", "inside_round": "в пределах типичного раунда", "above_round": "больше типичного раунда"}, "need_x": "Нужно на старте (нижняя точка — месяц {m})", "upto_x": "до {x}", "usual_for": "Обычно вкладывают при пути «{path}»", "gp_short": "Валовая прибыль за это время", "paths": {"bootstrap": "bootstrap", "pre_seed": "pre-seed", "seed": "seed", "series_a": "Series A"},
                "cap_sentence": "Пока накопленный кэш не дойдёт до нижней точки в месяце {m}, бизнес потратит {gross} ({items}) и за это время заработает {off} валовой прибыли; разница — {need} — это деньги, которые нужно иметь на старте.", "cap_round": "Это {text}.",
                "flags_intro": "Те же числа расчёта по рыночным оценкам рядом с ориентирами, по которым инвесторы обычно судят раннюю экономику. Это помощь в чтении таблицы, а не отдельный вывод.", "c_metric": "Показатель", "c_rule": "Ориентир", "c_model": "В расчёте", "c_verdict": "Итог",
                "r_ltvcac": "не ниже 3 (ниже 1 — каждый клиент убыточен)", "r_payback": "не дольше 18 месяцев", "r_be": "в пределах горизонта {n} месяцев; до M12 — сильно", "r_capital": "не больше обычного для пути «{path}» ({rng})", "verdicts": {"green": "в норме", "amber": "запас тонкий", "red": "проблема"}, "page_title": "Финансовая картина — бизнес по рыночным оценкам", "show": "Показать", "bridge_title": "Если команда права в одном допущении, а остальное — по рынку: как меняется потребность в капитале", "bridge_title_m": "Если одна метрика выйдет на уровень категории, а остальное — как измерено: как меняется выручка в последний месяц", "note_bridge": "столбики не складываются: допущения взаимодействуют", "t_title": "Насколько итог зависит от каждого рыночного допущения", "t_sub": "одно допущение за раз на худшем и лучшем краю его рыночного диапазона, остальное — рыночная середина; показана потребность в капитале", "t_base": "рыночный сценарий", "t_noteam": "цифры команды нет", "t_note": "зелёный — капитала нужно меньше, красный — больше", "rev_m": "Выручка в месяц", "cum": "Деньги на счёте нарастающим итогом", "cust": "Активные клиенты", "purch": "Покупок в месяц", "edge_lo": "Пессимистичный край", "edge_hi": "Оптимистичный край"}, "cmp_filled_note": "Сравнивать здесь пока нечего: как только по строке появится измеренное число, оно заменит рыночное.", "if_right": "если верны цифры команды",
        "bridge_hdr": ["Допущение", "Рынок → команда", "Потребность в капитале", "Выход в плюс", "Выручка, месяц {n}", "LTV / CAC", "Окупаемость"],
        "status": {"observed": "измерено", "founder_stated": "заявлено", "founder_guess": "оценка", "benchmarked": "цифры команды нет — взято рыночное значение"},
        "fill": {"unverified": "рыночных данных нет — взята цифра команды", "filled_from_market": "", "derived_from_channels": "таблица каналов"},
        "ue_cac": "Стоимость привлечения клиента (CAC, смешанная)", "ue_arpu": "Выручка с клиента в месяц", "ue_price": "Цена одной покупки",
        "ue_churn": "Отток в месяц", "ue_repeat": "Доля повторных покупок", "ue_margin": "Валовая маржа",
        "ue_ltv": "Пожизненная валовая прибыль с клиента (LTV, кэп 60 месяцев)", "ue_ltvcac": "LTV / CAC", "ue_payback": "Окупаемость клиента (месяцев, накопительно)",
        "ue_arpu3": "Нужная выручка с клиента в месяц для LTV/CAC = 3",
        "sc_be": "Выход в плюс (месяц)", "sc_cap": "Потребность в капитале", "sc_rev": "Выручка, месяц {n}", "sc_units": "{u}, месяц {n}", "sc_year": "Выручка, год {y}",
        "sc_cum": "Накопленный денежный поток, месяц {n}", "sc_burn": "Постоянные расходы в месяц", "customers": "Клиенты", "purchases": "Покупки",
        "cb_seg": "Размер сегмента", "cb_pen": "Проникновение аналогов", "cb_ref": "Ориентир по клиентам (3 года)", "cb_bu": "Клиентов по модели, месяц 36", "cb_pos": "Положение",
        "pos": {"above_comparables": "выше аналогов", "within_range": "в диапазоне", "far_below_comparables": "далеко ниже аналогов", "no_reference": "нет ориентира",
                 "unavailable": "сравнение с типичным раундом недоступно (нет проверенного ориентира в валюте модели)"},
        "growth_text": "Механика: {motion} · выход на 50 % мощности к месяцу {mid} · лаг цикла продаж {lag} мес",
        "capacity_text": "Новых клиентов в месяц на полной мощности — команда {f} · рынок {m} (диапазон бенчмарка {lo}–{hi})",
        "funnel_hdr": ["Шаг", "Значение", "Источник"],
        "dom": {"pricing": "цена", "project_value": "стоимость проекта", "projects_per_year": "проектов на клиента в год", "gmv_per_customer_month": "оборот на клиента в месяц",
                "take_rate": "комиссия", "gross_margin": "валовая маржа", "monthly_churn": "отток в месяц", "expansion": "рост чека", "repeat_rate": "доля повторов",
                "cac": "стоимость привлечения", "monthly_budget": "бюджет привлечения", "new_customers_per_month": "новых клиентов в месяц", "fte_cost": "стоимость сотрудника в месяц",
                "monthly_budget+new_customers_per_month": "бюджет и клиенты вместе"},
        "kpi_default": ["LTV / CAC — команда | рынок", "Окупаемость, мес — команда | рынок", "Выход в плюс, месяц — команда | рынок", "Потребность в капитале — команда | рынок",
                        "Выручка, месяц {n} — команда | рынок", "Вложения возвращены, месяц — команда | рынок"],
        "_measured": {"comparison": "Где вы стоите относительно категории", "assumptions": "Чего стоит подтянуть каждую метрику до уровня категории",
                      "bridge_intro": "Отправная точка — бизнес как измерен; одна метрика за раз подтягивается до уровня категории. Изменение выручки и потребности в капитале ранжирует метрики по тому, сколько стоит исправить каждую.",
                      "founder": "Измерено", "market": "Категория", "founder_case": "Бизнес как измерен", "market_case": "Бизнес на уровне категории",
                      "st_believes": "Измерено", "st_evidence": "Ориентир категории", "st_stakes": "Чего стоит выйти на уровень категории", "st_test": "Как сдвинуть",
                      "vs": "измерено {f} · категория {m}", "cmp_hdr": ["Метрика", "Измерено (источник)", "Категория (источник)", "Разрыв", "Если эта метрика выйдет на уровень категории (остальное — как измерено)"],
                      "kpi_default": ["LTV / CAC — измерено | категория", "Окупаемость, мес — измерено | категория", "Выход в плюс, месяц — измерено | категория", "Потребность в капитале — измерено | категория",
                                      "Выручка, месяц {n} — измерено | категория", "Вложения возвращены, месяц — измерено | категория"]},
    },
}


# ── docx helpers ─────────────────────────────────────────────

def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_color); tcPr.append(shd)


def set_cell(cell, text, bold=False, size=9, color=None, align=None):
    cell.text = ""; p = cell.paragraphs[0]
    run = p.add_run(str(text)); run.bold = bold; run.font.size = Pt(size); run.font.name = "Arial"
    if color: run.font.color.rgb = color
    if align: p.alignment = align
    p.paragraph_format.space_after = Pt(2)


def table(doc, rows, widths_cm=None, header=True, font_size=9):
    if not rows: return
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            if i == 0 and header: set_cell(c, val, bold=True, size=font_size, color=RGBColor(0xFF, 0xFF, 0xFF)); shade(c, "1F3864")
            else:
                set_cell(c, val, size=font_size)
                if i % 2 == 0: shade(c, "F5F7FA")
            if widths_cm: c.width = Cm(widths_cm[j])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def h(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for r in p.runs: r.font.name = "Arial"; r.font.color.rgb = NAVY
    if level == 1:
        pPr = p._p.get_or_add_pPr(); pbdr = OxmlElement("w:pBdr"); left = OxmlElement("w:left")
        left.set(qn("w:val"), "single"); left.set(qn("w:sz"), "24"); left.set(qn("w:space"), "6"); left.set(qn("w:color"), "1F3864"); pbdr.append(left); pPr.append(pbdr)
        shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "F2F4F8"); pPr.append(shd)
        p.paragraph_format.space_before = Pt(14); p.paragraph_format.space_after = Pt(6)
    return p


def para(doc, text, size=10.5, italic=False, color=None, after=6):
    p = doc.add_paragraph(); r = p.add_run(text); r.font.size = Pt(size); r.font.name = "Arial"; r.italic = italic
    if color: r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(after); return p


def lead_para(doc, text):
    """The section's finding: one bold sentence in navy, before the prose."""
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = True; r.font.size = Pt(11); r.font.name = "Arial"; r.font.color.rgb = NAVY
    p.paragraph_format.space_after = Pt(6); return p


def labelled(doc, label, text):
    p = doc.add_paragraph(); r = p.add_run(label + (" " if label.endswith((":", ",")) else ". ")); r.bold = True; r.font.name = "Arial"; r.font.size = Pt(10.5)
    r2 = p.add_run(text); r2.font.name = "Arial"; r2.font.size = Pt(10.5); p.paragraph_format.space_after = Pt(6)


# ── walking the report ───────────────────────────────────────

def _walk_strings(obj, path="", skip=IDENTITY_KEYS, question_ok=False):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip: continue
            yield from _walk_strings(v, f"{path}.{k}" if path else k, skip)
    elif isinstance(obj, list):
        for i, v in enumerate(obj): yield from _walk_strings(v, f"{path}[{i}]", skip)
    elif isinstance(obj, str):
        yield path, obj


# ── register lint ────────────────────────────────────────────
REGISTER_PATTERNS = [
    (r"\b(you|your|you're|yours)\b", "second person", re.I), (r"\b(ты|тебе|тебя|твой|твоя|твои|вы|вам|вас|ваш|ваша|ваши)\b", "second person", re.I),
    (r"\b(we|our|let's)\b", "first person", re.I), (r"\bus\b", "first person", 0), (r"\b(мы|нам|нас|наш|наша|наши|давай|давайте)\b", "first person", re.I),
    (r"\b(honestly|frankly|basically|as I said|as mentioned|by the way|to be fair|I think|I'd|I'm|in my view|great idea)\b", "chat connector", re.I),
    (r"\b(честно говоря|кстати|как я говорил|как уже|по сути|на самом деле|собственно|я думаю|думаю|мне кажется|честно|короче|наверное)\b|(?:^|\.\s+)ну,", "chat connector", re.I),
    (r"\b(said|says|put it|in (his|her) words)\b", "persona quoted as speaker", re.I), (r"\b(сказал[аи]?|говорит|по словам)\b", "persona quoted as speaker", re.I),
    (r"\?(\s|$)", "rhetorical question", 0),
    (r"\b(hobby|side gig|pretty|kind of|sort of)\b", "informal evaluation", re.I), (r"\b(подработка|хобби|прикольно|проедает|до неприличия|бьют|обходят)\b", "informal evaluation", re.I),
]


def lint_register(rep):
    out = []; startup = rep.get("startup", "")
    for path, s in _walk_strings(rep):
        if startup and len(startup) > 2: s = re.sub(r"(?<!\w)" + re.escape(startup) + r"(?!\w)", "STARTUP", s)
        s = re.sub(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){1,}\b", "LIBID", s)   # library ids (round.pre_seed.us.2025) and domains are not prose
        for pat, label, flags in REGISTER_PATTERNS:
            if label == "rhetorical question" and path.startswith(("next_90_days", "assumptions.stories")): continue   # an experiment title or a test may be a question   # a test or an open question is stated as a question
            for m in re.finditer(pat, s, flags=flags | re.M):
                a, b = max(0, m.start() - 30), min(len(s), m.end() + 30)
                out.append((path, label, s[a:b].replace("\n", " ")))
    return out


# ── model access & formatting ────────────────────────────────

def get_ref(model, ref):
    cur = model
    for part in ref.split("."):
        if isinstance(cur, list):
            try: cur = cur[int(part)]
            except (ValueError, IndexError): raise KeyError(f"ref {ref!r}: index {part!r} not found")
        elif isinstance(cur, dict) and part in cur: cur = cur[part]
        else: raise KeyError(f"ref {ref!r}: {part!r} not found")
    if isinstance(cur, (dict, list)):
        raise KeyError(f"ref {ref!r} points at a structure, not a value")
    return cur


def field_kind(ref, model):
    """What kind of number a model field holds, from its path; None = unknown (only 'text' is safe)."""
    parts = ref.split("."); last = parts[-1]
    if ("bridge" in parts or "bridge_to_market" in parts or "bridge_by_domain" in parts or "bridge_to_market_by_domain" in parts) and len(parts) >= 2 and parts[-2] in ("peak_capital_need", "revenue_end", "ltv_cac", "breakeven_month", "payback_months"):
        return {"peak_capital_need": "money", "revenue_end": "money" if last != "month" else "int", "ltv_cac": "mult", "breakeven_month": "month", "payback_months": "months"}[parts[-2]]
    heads = [h_ for h_ in ("comparison", "bridge", "bridge_to_market", "bridge_by_domain", "bridge_to_market_by_domain") if h_ in parts]
    if heads:
        try:
            hi_ = parts.index(heads[0]); depth = hi_ + (3 if heads[0].endswith("by_domain") and parts[hi_ - 1:hi_] == ["combined"] else 2)
            row = model
            for part in parts[:depth]:
                row = row[int(part)] if isinstance(row, list) else row[part]
            k = row.get("kind")
            if last in ("founder", "market", "market_low", "market_high", "measured", "category"):
                return {"money": "money", "pct": "pct", "count": "int"}.get(k)
            if last == "gap_ratio": return "mult"
        except Exception:
            return None
    if last in ("ltv_cac", "ratio_to_reference"): return "mult"
    if last == "payback_months": return "months"
    if last == "breakeven_month": return "month"
    if last in ("month", "months", "customers", "new_customers", "starting_customers", "segment_size", "reference_customers_3y", "bottom_up_customers_m36", "free_months", "repeat_interval_months", "ltv_horizon_months", "projects_per_year"): return "int"
    if last.endswith("_pct") or last in ("comparable_penetration_pct", "implied_share_pct"): return "pct"
    if last in ("mrr", "cumulative", "net_cash_flow", "ltv", "ltv_uncapped", "arpu", "arpu0", "arpu_actual", "arpu_for_ltv_cac_3", "blended_cac", "monthly_fixed_burn", "upfront_investment",
                "fte_cost", "monthly_budget", "peak_capital_need", "cumulative_m_last", "upfront_investment_total", "price", "project_value", "gmv_per_customer_month", "starting_mrr", "delta",
                "y1", "y2", "y3", "y4", "y5", "y6", "y7", "y8", "y9", "y10", "market", "founder", "if_founder_right"):
        return "money" if last not in ("market", "founder", "if_founder_right") else None
    if last in ("new_customers_per_month_full", "ramp_mid_month", "sales_cycle_months"): return "int"
    return None


COMPATIBLE = {"money": {"money"}, "pct": {"pct"}, "mult": {"mult"}, "months": {"months", "int"}, "month": {"month", "int"}, "int": {"int", "text"}, None: set(FORMATS) - {"text"}, "str": {"text"}}


def money(x, cur):
    return fmt_money(x, cur)


MFMT = "M{v}"   # month label format; build() sets it from the labels ("M9" / "9-й мес.")


def mlabel(v):
    return getattr(chart_style, "MFMT", MFMT).format(v=v)   # chart_style holds the live value: the CLI runs this file as __main__ while build_pdf imports it as a module


def fmt_value(v, fmt, cur, T):
    if fmt == "money": return money(v, cur)
    if fmt == "mult": return fmt_mult(v) if v is not None else T.get("no_cash_cac", "∞ (no cash CAC)")
    if fmt == "months": return f"{v:.0f}" if v else T["none"]
    if fmt == "month": return mlabel(v) if v else T["not_within"].replace("{n}", str(T.get("_n", "")))
    if fmt == "pct": return fmt_pct(v)
    if fmt == "int": return f"{v:,.0f}" if v is not None else "—"
    if fmt == "text":
        if isinstance(v, float): return f"{v:g}"
        if isinstance(v, str) and v in T.get("enum", {}): return T["enum"][v]
        return str(v) if v is not None else "—"
    raise ValueError(f"unknown format {fmt!r}")


def round_text(model, cur, T):
    """'above the typical bootstrap outlay (up to €50k) by €38k' — the funding-path comparison as a phrase a founder can read."""
    c = model.get("capital_vs_round") or {}
    pos = c.get("position")
    if pos not in ("below_round", "inside_round", "above_round"): return T["enum"].get(pos or "unavailable", T["enum"]["unavailable"])
    path = T["paths"].get(c.get("path"), c.get("path"))
    lo, hi = c.get("round_low_model_ccy", c["round_low"]), c.get("round_high_model_ccy", c["round_high"])
    rng = (money(lo, cur) + "–" + money(hi, cur)) if lo else T["upto"].format(x=money(hi, cur))
    diff = abs((c.get("capital_need") or 0) - (hi if pos == "above_round" else lo))
    s = T["round_text"][pos].format(path=path, rng=rng, diff=money(diff, cur))
    cc = model.get("capital_vs_cash")
    if cc:
        s += "; " + (T["cash_text"]["enough"] if cc["position"] == "enough" else T["cash_text"]["short"]).format(cash=money(cc["cash_on_hand"], cur), gap=money(abs(cc["gap"]), cur), m=cc.get("cash_out_month") or "")
    return s


def render_placeholders(obj, model, cur, T):
    if isinstance(obj, dict): return {k: (v if k in IDENTITY_KEYS | NO_PLACEHOLDER_KEYS else render_placeholders(v, model, cur, T)) for k, v in obj.items()}
    if isinstance(obj, list): return [render_placeholders(v, model, cur, T) for v in obj]
    if isinstance(obj, str):
        def sub(m):
            if m.group(1) == "capital_vs_round.position": return round_text(model, cur, T)   # a sentence with the path and the sum, not an enum
            try: return fmt_value(get_ref(model, m.group(1)), m.group(2) or "text", cur, T)
            except (KeyError, TypeError, ValueError) as e: raise ValueError(f"placeholder {m.group(0)}: {e}")
        return PLACEHOLDER.sub(sub, obj).replace("мес..", "мес.")   # a month label ending a sentence would double the full stop
    return obj


def lead(model, rep):
    """(cases dict, bridge, comparison, months, combined-or-None, line name)"""
    if "lines" in model:
        name = rep.get("line")
        if not name: raise ValueError(f"multi-line model: report.json must name the leading line in 'line'; have {list(model['lines'])}")
        if name not in model["lines"]: raise ValueError(f"line {name!r} not in model; have {list(model['lines'])}")
        ln = model["lines"][name]
        return ln["cases"], ln["bridge"], ln["comparison"], model["months"], model["combined"], name
    return model["cases"], model["bridge"], model["comparison"], model["months"], None, None


def default_kpis(model, rep, T):
    cases, br, cmp_, n, comb, name = lead(model, rep)
    base = f"lines.{name}." if name else ""
    labs = [x.replace("{n}", str(n)) for x in T["kpi_default"]]
    pair = lambda i, ref, fmt: {"label": labs[i], "pair": [f"{base}cases.founder.{ref}", f"{base}cases.market.{ref}"] if not (comb and ref.startswith("@")) else [f"combined.founder.{ref[1:]}", f"combined.market.{ref[1:]}"], "fmt": fmt}
    k = [pair(0, "unit_economics.ltv_cac_headline", "mult"), pair(1, "unit_economics.payback_headline", "months")]   # loaded ratio when a selling share of payroll is given
    if comb:
        k += [pair(2, "@breakeven_month", "months"), pair(3, "@peak_capital_need", "money"), pair(4, f"@projection.{n-1}.mrr", "money"), pair(5, "@cash_recovery_month", "months")]
    else:
        k += [pair(2, "breakeven_month", "months"), pair(3, "peak_capital_need", "money"), pair(4, "milestones.end.mrr", "money"), pair(5, "cash_recovery_month", "months")]
    hints = T.get("kpi_hint") or [""] * 6
    for i, kk in enumerate(k): kk["hint"] = hints[i] if i < len(hints) else ""
    return k


def kpi_value(k, model, cur, T):
    if "pair" in k: return " | ".join(fmt_value(get_ref(model, r), k["fmt"], cur, T) for r in k["pair"])
    return fmt_value(get_ref(model, k["ref"]), k.get("fmt", "text"), cur, T)


# ── generated tables ─────────────────────────────────────────

def _dv(kind, v, cur):
    if v is None: return "—"
    if kind == "pct": return fmt_pct(v, 2)
    if kind == "money": return money(v, cur) if abs(v) >= 1000 else f"{cur}{v:g}".replace(".", chart_style.DEC)
    return f"{v:g}".replace(".", chart_style.DEC)


def gen_comparison(cmp_rows, br, T, cur, notes, line=None, rank=None, measured=False):
    """Rows: assumption · founder (status) · market (source) · gap · bridge effect. Sixth element = ranking key (combined when given)."""
    eff = {b["domain"]: b for b in br}
    rows = []
    for r in cmp_rows:
        d = r["domain"]; kind = r["kind"]; lab = (f"{line} · " if line else "") + T["dom"].get(d, r["label"])
        st = T["status"].get(r["status"], r["status"]); fl = T["fill"].get(r["fill"], "") if r["fill"] else ""
        f_txt = f"{_dv(kind, r['founder'], cur)} ({st}{'; ' + fl if fl else ''})"
        mk = _dv(kind, r["market"], cur) + (f" [{_dv(kind, r['market_low'], cur)}–{_dv(kind, r['market_high'], cur)}]" if r["market_low"] != r["market_high"] else "")
        src = notes.get(d) or r["source"] or T["fill"]["unverified"]
        src = src if len(src) <= 48 else src[:46].rstrip() + "…"      # page-1 cell: the full source is in the appendix
        m_txt = f"{mk} · {src}"
        gap = "—" if r["gap_ratio"] is None else ("∞" if isinstance(r["gap_ratio"], str) else fmt_mult(r["gap_ratio"]))
        b = eff.get(d)
        if b and measured:
            be = lambda v: mlabel(v) if v else T["none"]
            lc = lambda v: f"{v:.1f}" if v is not None else "∞"
            e_txt = (f"{T['rev_short']} {money(b['revenue_end']['measured'], cur)} → {money(b['revenue_end']['if_at_category'], cur)} · {T['cap_short']} {money(b['peak_capital_need']['measured'], cur)} → {money(b['peak_capital_need']['if_at_category'], cur)} · "
                     f"LTV/CAC {lc(b['ltv_cac']['measured'])} → {lc(b['ltv_cac']['if_at_category'])} · {T['be_short']} {be(b['breakeven_month']['measured'])} → {be(b['breakeven_month']['if_at_category'])}")
            key = abs((rank or {}).get((line, d), b["revenue_end"]["delta"]) or 0)
        elif b:
            be = lambda v: mlabel(v) if v else T["none"]
            lc = lambda v: f"{v:.1f}" if v is not None else "∞"
            e_txt = (f"{T['cap_short']} {money(b['peak_capital_need']['market'], cur)} → {money(b['peak_capital_need']['if_founder_right'], cur)} · "
                     f"LTV/CAC {lc(b['ltv_cac']['market'])} → {lc(b['ltv_cac']['if_founder_right'])} · {T['be_short']} {be(b['breakeven_month']['market'])} → {be(b['breakeven_month']['if_founder_right'])}")
            key = abs((rank or {}).get((line, d), b["peak_capital_need"]["delta"]) or 0)
        else:
            e_txt = "—"; key = -1
        rows.append([lab, f_txt, m_txt, gap, e_txt, key])
    return rows


def gen_bridge(br, T, cur, n, line=None):
    hdr = [x.replace("{n}", str(n)) for x in T["bridge_hdr"]]; rows = [hdr]
    be = lambda v: mlabel(v) if v else T["none"]; pb = lambda v: str(v) if v else T["none"]
    for b in br:
        rows.append([(f"{line} · " if line else "") + T["dom"].get(b["domain"], b["label"]), ("—" if b["kind"] == "joint" else f"{_dv(b['kind'], b['market'], cur)} → {_dv(b['kind'], b['founder'], cur)}"),
                     f"{money(b['peak_capital_need']['market'], cur)} → {money(b['peak_capital_need']['if_founder_right'], cur)}",
                     f"{be(b['breakeven_month']['market'])} → {be(b['breakeven_month']['if_founder_right'])}",
                     f"{money(b['revenue_end']['market'], cur)} → {money(b['revenue_end']['if_founder_right'], cur)}",
                     f"{b['ltv_cac']['market'] if b['ltv_cac']['market'] is not None else '∞'}× → {b['ltv_cac']['if_founder_right'] if b['ltv_cac']['if_founder_right'] is not None else '∞'}×", f"{pb(b['payback_months']['market'])} → {pb(b['payback_months']['if_founder_right'])}"])
    return rows


def gen_unit_economics(cases, T, cur, title):
    unit = cases["market"]["inputs"]["revenue_unit"]
    rows = [[title] + [T[c] for c in CASES]]
    g = lambda f: [f(cases[c]) for c in CASES]
    rows.append([T["ue_cac"]] + g(lambda s: money(s["inputs"]["blended_cac"], cur)))
    if unit == "one_off":
        rows.append([T["ue_price"]] + g(lambda s: money(s["inputs"]["price"], cur))); rows.append([T["ue_repeat"]] + g(lambda s: fmt_pct(s['inputs']['repeat_rate_pct'])))
    else:
        rows.append([T["ue_arpu"]] + g(lambda s: money(s["inputs"]["arpu0"], cur))); rows.append([T["ue_churn"]] + g(lambda s: fmt_pct(s['inputs']['monthly_churn_pct'])))
    rows.append([T["ue_margin"]] + g(lambda s: fmt_pct(s['inputs']['gross_margin_pct'])))
    rows.append([T["ue_ltv"]] + g(lambda s: money(s["unit_economics"]["ltv"], cur)))
    rows.append([T["ue_ltvcac"]] + g(lambda s: fmt_mult(s["unit_economics"]["ltv_cac"]) if s["unit_economics"]["ltv_cac"] is not None else T["no_cash_cac"]))
    rows.append([T["ue_payback"]] + g(lambda s: str(s["unit_economics"]["payback_months"]) if s["unit_economics"]["payback_months"] else T["never"]))
    if any((cases[c]["unit_economics"].get("sales_share_of_payroll") or 0) > 0 for c in CASES):   # sales-led: the loaded ratio is the one that matters
        rows.append([T["ue_cac_loaded"]] + g(lambda s: money(s["unit_economics"]["cac_loaded"], cur)))
        rows.append([T["ue_ltvcac_loaded"]] + g(lambda s: fmt_mult(s["unit_economics"]["ltv_cac_loaded"]) if s["unit_economics"].get("ltv_cac_loaded") is not None else "—"))
        rows.append([T["ue_payback_loaded"]] + g(lambda s: str(s["unit_economics"]["payback_loaded"]) if s["unit_economics"].get("payback_loaded") else T["never"]))
    if any(cases[c]["inputs"].get("founder_time_cost_per_customer") for c in CASES):
        rows.append([T["ue_ltvcac_time"]] + g(lambda s: fmt_mult(s['unit_economics']['ltv_cac_incl_time']) if s["unit_economics"].get("ltv_cac_incl_time") is not None else "—"))
        rows.append([T["ue_payback_time"]] + g(lambda s: str(s["unit_economics"]["payback_incl_time"]) if s["unit_economics"].get("payback_incl_time") else T["never"]))
    return rows


def gen_outcomes(model, rep, T, cur):
    cases, br, cmp_, n, comb, name = lead(model, rep)
    rows = [[""] + [T[c] for c in CASES]]
    if comb:
        for y in comb["market"]["revenue_by_year"]:
            rows.append([T["sc_year"].format(y=y[1:])] + [money(comb[c]["revenue_by_year"][y], cur) for c in CASES])
        rows.append([T["sc_be"]] + [mlabel(comb[c]['breakeven_month']) if comb[c]["breakeven_month"] else T["not_within"].replace("{n}", str(n)) for c in CASES])
        rows.append([T["sc_cap"]] + [money(comb[c]["peak_capital_need"], cur) for c in CASES])
        rows.append([T["sc_rev"].format(n=n)] + [money(comb[c]["projection"][-1]["mrr"], cur) for c in CASES])
        rows.append([T["sc_cum"].format(n=n)] + [money(comb[c]["cumulative_m_last"], cur) for c in CASES])
        for ln, r in model["lines"].items():
            rows.append([f"{T['line']} {ln}: " + T["sc_rev"].format(n=n)] + [money(r["cases"][c]["milestones"]["end"]["mrr"], cur) for c in CASES])
    else:
        rows.append([T["sc_be"]] + [mlabel(cases[c]['breakeven_month']) if cases[c]["breakeven_month"] else T["not_within"].replace("{n}", str(n)) for c in CASES])
        rows.append([T["sc_cap"]] + [money(cases[c]["peak_capital_need"], cur) for c in CASES])
        seen_m = set()
        for k, ms in cases["market"]["milestones"].items():
            if ms["month"] in seen_m: continue   # "end" repeats m36 on a 36-month horizon
            seen_m.add(ms["month"])
            rows.append([T["sc_rev"].format(n=ms["month"])] + [money(cases[c]["milestones"][k]["mrr"], cur) for c in CASES])
        ul = T["purchases"] if cases["market"]["milestones"]["end"].get("units_label") == "purchases" else T["customers"]
        rows.append([T["sc_units"].format(u=ul, n=n)] + [f"{cases[c]['milestones']['end']['customers']:,.0f}" for c in CASES])
        rows.append([T["sc_burn"]] + [money(cases[c]["inputs"]["monthly_fixed_burn"], cur) for c in CASES])
    return rows


def gen_comparable(cases, T, cur):
    c = cases["market"].get("comparable_benchmark")
    if not c or "note" in c: return None
    t = lambda s: cases[s]["comparable_benchmark"]
    return [[""] + [T[x] for x in CASES], [T["cb_seg"]] + [f"{t(s)['segment_size']:,.0f}" for s in CASES],
            [T["cb_pen"]] + [f"{t(s)['comparable_penetration_pct']:.1f} %" for s in CASES], [T["cb_ref"]] + [f"{t(s)['reference_customers_3y']:,.0f}" for s in CASES],
            [T["cb_bu"]] + [f"{t(s)['bottom_up_customers_m36']:,.0f}" for s in CASES], [T["cb_pos"]] + [T["pos"].get(t(s)["position"], t(s)["position"]) for s in CASES]]


def gen_growth(cases, cmp_rows, T):
    g = cases["market"]["growth"]
    text = T["growth_text"].format(motion=g["motion"], mid=f"{g['ramp_mid_month']:.0f}", lag=g["sales_cycle_months"])
    funnel = [T["funnel_hdr"]] + [[str(f.get("step", "")), str(f.get("value", "")), str(f.get("source", ""))] for f in g.get("funnel", [])]
    nc = next((r for r in cmp_rows if r["domain"] == "new_customers_per_month"), None)
    cap = T["capacity_text"].format(f=f"{nc['founder']:g}", m=f"{nc['market']:g}", lo=f"{nc['market_low']:g}", hi=f"{nc['market_high']:g}") if nc else ""
    return text, funnel, cap


# ── number verification ──────────────────────────────────────
_NUM = re.compile(r"(?<![.,\d])[−\-+]?(?:\d{1,3}(?:[ \xa0\u202f]\d{3})+|\d{1,3}(?:\.\d{3})+(?![.,]\d)|\d+(?:,\d{3})+|\d+)(?:[.,]\d+)?(?:e[+-]?\d+)?(?:\s?(?:тыс\.?|млн\.?|млрд\.?|k|K|M|bn|B|mo|x)(?![A-Za-zА-Яа-я]))?[A-Za-zА-Яа-я%‰×]*")
_YEAR = re.compile(r"^(19|20)\d\d$")


def _parse_num(tok):
    """→ (value, half display unit, marked) or None. Any glued letters/symbols count as a marker; k/M/тыс/млн/bn/B scale.
    European thousands (1.000.000) and decimal commas (1,5) are understood."""
    t = tok.strip().replace("\u2212", "-")
    for sp in (" ", "\u202f", "\xa0", "\u2009"): t = t.replace(sp, "")
    t = t.lstrip("€$£₽")
    m = re.match(r"^([+-]?[\d,.]*?(?:e[+-]?\d+)?)([A-Za-zА-Яа-я%‰×].*)?$", t)
    if not m: return None
    num, suf = m.group(1), (m.group(2) or "").rstrip(".")
    if not num.endswith(("e",)) and re.search(r"e[+-]?\d+$", num) is None: pass
    if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", num): num = num.replace(".", "")            # 1.000 / 9.999 → thousands
    elif num.count(",") == 1 and "." not in num and len(num.split(",")[-1]) <= 2: num = num.replace(",", ".")   # 1,5 → 1.5
    else: num = num.replace(",", "")
    try: v = float(num)
    except ValueError: return None
    mult = {"k": 1e3, "K": 1e3, "тыс": 1e3, "m": 1e6, "M": 1e6, "млн": 1e6, "mn": 1e6, "MM": 1e6, "bn": 1e9, "B": 1e9, "млрд": 1e9}.get(suf, 1.0)
    dec = len(num.split(".")[1]) if "." in num else 0
    return v * mult, 0.5 * mult / (10 ** dec), bool(suf)


def _norm(s):
    return re.sub(r"\s+", " ", str(s).replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ")).strip()


def verify_free_text(rep):
    """Every number in free text (placeholders removed) must be declared in manual_numbers. `rep` is UNRENDERED."""
    manual = []
    for m in rep.get("manual_numbers", []):
        if not (isinstance(m, dict) and str(m.get("value", "")).strip() and str(m.get("field", "")).strip() and str(m.get("source", "")).strip()):
            raise ValueError(f"manual_numbers entries need value, field and source: {m!r}")
        where = m.get("where")
        if not (isinstance(where, list) and where and all(isinstance(w, str) and w.strip() for w in where)):
            raise ValueError(f"manual_numbers entry {m.get('value')!r} needs 'where': the report paths it is used in (e.g. [\"story[2]\", \"next_90_days[0].threshold\"])")
        ctx = str(m.get("context", "") or "").strip()
        if not ctx:
            raise ValueError(f"manual_numbers entry {m.get('value')!r} needs 'context': the phrase the number appears in, e.g. \"10 лидов\" or \"за 90 дней\" — it binds the value to its meaning")
        if _parse_num(str(m["value"])) is None or not any(abs(_parse_num(tok.group(0))[0] - _parse_num(str(m["value"]))[0]) <= 1e-9 for tok in _NUM.finditer(ctx) if _parse_num(tok.group(0))):
            raise ValueError(f"manual_numbers entry {m.get('value')!r}: 'context' must contain the number itself ({ctx!r})")
        if any(tok in str(m.get("source", "")).lower() for tok in ("model", "bridge", "cases.", "comparison", "combined")):
            raise ValueError(f"manual_numbers entry {m.get('value')!r}: a number whose source is the model must be a {{{{ref|fmt}}}} placeholder, not a manual number")
        p = _parse_num(str(m["value"]))
        if p: manual.append((p[0], [w.strip() for w in where], _norm(PLACEHOLDER.sub(" ", ctx))))
    bad = []
    _DATE = re.compile(r"(?<!\d)(?:\d{1,2}\.)?\d{2}\.(?:19|20)\d{2}(?!\d)")   # 02.2025, 14.02.2025
    _IDENT = re.compile(r"^\d+(?!(?:mo|bn|тыс|млн|млрд)\b)[A-Za-zА-Яа-я]{2,}$")   # a brand-like token: digits glued to a word that is not a unit
    _URL = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+/\S*")
    for path, s0 in _walk_strings(rep):
        if re.fullmatch(r"appendix\.evidence\[\d+\]\[0\]", path) and re.fullmatch(r"\s*\d{1,3}\s*", s0 or ""): continue   # the row-number column
        s = _DATE.sub(lambda m: " " * len(m.group(0)), PLACEHOLDER.sub(" ", s0))
        s = _URL.sub(lambda m: " " * len(m.group(0)), s)   # digits inside URLs are not figures
        for m in _NUM.finditer(s):
            tok = m.group(0)
            glued_prefix = bool(re.match(r"[A-Za-zА-Яа-я]", s[max(0, m.start() - 1):m.start()]))   # M36, Q4, x45: a letter glued to the number is a unit in disguise
            p = _parse_num(tok)
            if p is None: continue
            if _IDENT.match(tok) and not glued_prefix: continue   # 2pr, 4ocean, 1password: digits + a word are a name, not a number
            v, half, glued = p
            before = s[max(0, m.start() - 1):m.start()]
            marked = glued or glued_prefix or before in ("€", "$", "£", "₽") or s[m.end():m.end() + 2].strip().startswith(("%", "×", "x"))
            if _YEAR.match(tok) and not marked: continue
            if not marked and abs(v) < 10 and float(v).is_integer(): continue
            window = _norm(s[max(0, m.start() - 60):m.end() + 60])   # s = the text with placeholders blanked, same as the context is normalised
            if any(abs(v - x) <= max(half, 0.001 * abs(x)) and any(path == w or path.startswith(w + ".") or path.startswith(w + "[") for w in wh) and ctx in window for x, wh, ctx in manual): continue
            bad.append((path, tok, re.sub(r"\s+", " ", s[max(0, m.start() - 40):m.end() + 40])))   # offsets are in the placeholder-blanked text, so the window is taken from it too
    return bad


def check_placeholders(rep, model):
    errs = []
    for path, s0 in _walk_strings(rep):
        if path.split(".")[0].split("[")[0] in NO_PLACEHOLDER_KEYS:
            if "{{" in s0 or "}}" in s0: errs.append(f"placeholders are not allowed in {path}; write the number in the text and declare it")
            continue
        for m in PLACEHOLDER.finditer(s0):
            ref, fmt = m.group(1), m.group(2) or "text"
            if fmt not in FORMATS: errs.append(f"placeholder in {path}: unknown format {fmt!r}; use one of {FORMATS}"); continue
            try: val = get_ref(model, ref)
            except KeyError as e: errs.append(f"placeholder in {path}: {e}"); continue
            kind = "str" if isinstance(val, str) or val is None and fmt != "text" else field_kind(ref, model)
            if isinstance(val, bool): errs.append(f"placeholder in {path}: {ref} is not a number"); continue
            if fmt not in COMPATIBLE.get(kind, set(FORMATS)):
                errs.append(f"placeholder in {path}: {ref} is a {kind} field; format {fmt!r} would mislabel it (allowed: {sorted(COMPATIBLE[kind])})")
        if ANY_BRACES.search(PLACEHOLDER.sub("", s0)):
            errs.append(f"malformed placeholder in {path}: stray '{{{{' or '}}}}' — use {{{{ref|fmt}}}}")
    return errs


def check_rendered(rep):
    return [f"unrendered placeholder text in {path}" for path, s0 in _walk_strings(rep) if ANY_BRACES.search(s0)]


def required_charts(model, rep):
    cases, br, cmp_, n, comb, name = lead(model, rep)
    return {"charts.json": ["chart_mrr.png", "chart_cash.png", "chart_customers.png"], "dashboard.json": ["dashboard.png"] + (["bridge.png"] if br else [])}


def check_charts(charts_dir, model, rep):
    from build_workbook import model_hash, file_hash
    want = model_hash(model); errs = []
    for side, files in required_charts(model, rep).items():
        fp = os.path.join(charts_dir, side)
        if not os.path.exists(fp): errs.append(f"{side} missing in {charts_dir}: rebuild the charts from this model"); continue
        st = json.load(open(fp))
        import hashlib
        body = {k: v for k, v in st.items() if k != "sig"}
        if st.get("sig") != hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]:
            errs.append(f"{side} was edited by hand (signature mismatch) — rebuild the charts"); continue
        if st.get("model_hash") != want: errs.append(f"{side}: charts were generated from a different model ({st.get('model_hash')} ≠ {want})")
        for f in files:
            fp2 = os.path.join(charts_dir, f)
            if not os.path.exists(fp2): errs.append(f"{f} missing"); continue
            if st.get("png_hash", {}).get(f) != file_hash(fp2): errs.append(f"{f}: hash differs from {side} (image replaced or build interrupted)")
        ctx = st.get("context") or {}
        want_ctx = {"lang": str(rep.get("lang", "en")).lower(), "currency": str(rep.get("currency", "$"))}
        if side == "dashboard.json": want_ctx["line"] = rep.get("line") if "lines" in model else None
        for k, v in want_ctx.items():
            if ctx.get(k) != v: errs.append(f"{side} was rendered for {k}={ctx.get(k)!r}, the report needs {k}={v!r} — rebuild with the matching --line/--lang/--currency")
    return errs


def check_labels(rep, T_base):
    errs = []; ov = rep.get("labels") or {}
    if not isinstance(ov, dict): return ["labels must be an object"]
    for k, v in ov.items():
        if k not in T_base or k == "_measured": errs.append(f"labels.{k}: unknown label key"); continue
        base = T_base[k]
        if isinstance(base, dict):
            if not isinstance(v, dict) or set(v) != set(base): errs.append(f"labels.{k}: must map exactly {sorted(base)}")
        elif isinstance(base, list):
            if not isinstance(v, list) or len(v) != len(base): errs.append(f"labels.{k}: must be a list of {len(base)} strings")
        elif not isinstance(v, str) or not v.strip(): errs.append(f"labels.{k}: must be a non-empty string")
    return errs


def check_schema(rep):
    """Types before anything else, so malformed input fails with a message and not a traceback."""
    errs = []
    S = lambda k: isinstance(rep.get(k), str)
    for k in ("startup", "verdict_text", "evidence_basis"):
        if not S(k): errs.append(f"{k} must be a string")
    if not (isinstance(rep.get("story"), list) and all(isinstance(x, str) for x in rep["story"])): errs.append("story must be a list of strings")
    if "conditions" in rep and not (isinstance(rep["conditions"], list) and all(isinstance(x, str) for x in rep["conditions"])): errs.append("conditions must be a list of strings")
    if "kill_criterion" in rep and not (isinstance(rep["kill_criterion"], dict) and all(isinstance(rep["kill_criterion"].get(f, ""), str) for f in ("metric", "threshold", "what_model_shows"))): errs.append("kill_criterion must be {metric, threshold, what_model_shows}")
    if "labels" in rep and not isinstance(rep["labels"], dict): errs.append("labels must be an object")
    for k in ("market_case", "founder_case", "competition", "assumptions"):
        o = rep.get(k)
        if not isinstance(o, dict): errs.append(f"{k} must be an object"); continue
        if not isinstance(o.get("lead", ""), str): errs.append(f"{k}.lead must be a string")
        if k != "assumptions" and not (isinstance(o.get("paragraphs", []), list) and all(isinstance(x, str) for x in o.get("paragraphs", []))): errs.append(f"{k}.paragraphs must be a list of strings")
    cp = rep.get("competition") or {}
    if not (isinstance(cp.get("dimensions", []), list) and all(isinstance(x, dict) and all(isinstance(x.get(f, ""), str) for f in ("key", "label", "why")) for x in cp.get("dimensions", []))): errs.append("competition.dimensions must be a list of {key, label, why}")
    if not (isinstance(cp.get("rows", []), list) and all(isinstance(x, dict) and all(isinstance(x.get(f, ""), str) for f in ("name", "layer", "price", "source")) and isinstance(x.get("cells", {}), dict) and isinstance(x.get("self", False), bool) for x in cp.get("rows", []))): errs.append("competition.rows must be a list of {name, layer, price, cells{}, source, self}")
    st = (rep.get("assumptions") or {}).get("stories", [])
    if not (isinstance(st, list) and all(isinstance(x, dict) and all(isinstance(x.get(f, ""), str) for f in ("domain", "line", "belief", "evidence", "stakes", "test")) for x in st)): errs.append("assumptions.stories must be a list of objects with string fields")
    for k, fields in (("next_90_days", ("title", "what", "how", "threshold", "domain")), ("risks", ("title", "what", "impact", "signal", "action", "likelihood", "reversibility"))):
        lst = rep.get(k, [])
        if not (isinstance(lst, list) and all(isinstance(x, dict) and all(isinstance(x.get(f, ""), str) for f in fields) for x in lst)): errs.append(f"{k} must be a list of objects with string fields {fields}")
    kp = rep.get("kpis", [])
    if not (isinstance(kp, list) and all(isinstance(x, dict) and isinstance(x.get("label", ""), str) for x in kp)): errs.append("kpis must be a list of objects")
    for x in kp if isinstance(kp, list) else []:
        if isinstance(x, dict) and "pair" in x and not (isinstance(x["pair"], list) and len(x["pair"]) == 2 and all(isinstance(r, str) for r in x["pair"])): errs.append("kpi.pair must be exactly two refs")
    ap = rep.get("appendix") or {}
    ev = ap.get("evidence") if isinstance(ap, dict) else None
    if not (isinstance(ev, list) and ev and all(isinstance(r, list) and all(isinstance(c, str) for c in r) for r in ev)): errs.append("appendix.evidence must be a list of rows of strings")
    elif len({len(r) for r in ev}) != 1: errs.append("appendix.evidence rows must all have the same length")
    notes = (rep.get("comparison") or {}).get("notes", {}) if isinstance(rep.get("comparison"), dict) else {}
    if not (isinstance(notes, dict) and all(isinstance(v, str) for v in notes.values())): errs.append("comparison.notes must map domain → string")
    mn = rep.get("manual_numbers", [])
    if not (isinstance(mn, list) and all(isinstance(x, dict) for x in mn)): errs.append("manual_numbers must be a list of objects")
    return errs


MIN_LEN = {"story_sentence": 40, "lead": 30, "paragraph": 80, "story_part": 40, "threshold": 15, "risk_part": 40, "risk_signal": 25}


def _short(s, n): return len(str(s or "").strip()) < n


def check_story_bindings(rep, model):
    """Every bridge placeholder inside a story must point at THAT story's domain and line. Runs on the UNRENDERED report."""
    errs = []
    comb = "lines" in model
    for i, s_ in enumerate((rep.get("assumptions") or {}).get("stories") or []):
        sd, sl = s_.get("domain"), (s_.get("line") if comb else None)
        own = {b_i for b_i, bb in enumerate((model["lines"][sl]["bridge"] if comb else model["bridge"]) if (not comb or sl in model["lines"]) else []) if bb["domain"] == sd}
        cown = {c_i for c_i, cb_ in enumerate(model["combined"]["bridge"]) if cb_["line"] == sl and cb_["domain"] == sd} if comb else set()
        own_m = {b_i for b_i, bb in enumerate((model["lines"][sl].get("bridge_to_market", []) if comb else model.get("bridge_to_market", [])) if (not comb or sl in model["lines"]) else []) if bb["domain"] == sd}
        cown_m = {c_i for c_i, cb_ in enumerate(model["combined"].get("bridge_to_market", [])) if cb_["line"] == sl and cb_["domain"] == sd} if comb else set()
        for m_ in PLACEHOLDER.finditer(" ".join(str(s_.get(k, "")) for k in ("stakes", "belief", "evidence", "test"))):
            ref = m_.group(1); parts = ref.split(".")
            bad = False
            for name_, own_set, cown_set in (("bridge", own, cown), ("bridge_to_market", own_m, cown_m)):
                if name_ in parts:
                    bi = parts.index(name_); idx = parts[bi + 1] if len(parts) > bi + 1 else ""
                    if parts[bi - 1:bi] == ["combined"]: bad = bad or not (idx.isdigit() and int(idx) in cown_set)
                    else: bad = bad or not (idx.isdigit() and int(idx) in own_set) or (comb and parts[:2] != ["lines", sl])
            for name_ in ("bridge_by_domain", "bridge_to_market_by_domain"):
                if name_ in parts:
                    bi = parts.index(name_)
                    if parts[bi - 1:bi] == ["combined"]: bad = bad or parts[bi + 1:bi + 3] != [sl, sd]
                    else: bad = bad or parts[bi + 1:bi + 2] != [sd] or (comb and parts[:2] != ["lines", sl])
            if bad: errs.append(f"assumptions.stories[{i}] ({sd}): {ref} is the effect of another assumption or line")
    return errs


def page1_rows(rep):
    n = rep.get("page1_rows", PAGE1_ROWS)
    return n if isinstance(n, int) and 3 <= n <= 5 else PAGE1_ROWS


def check_page1_budget(rep):
    errs = []
    if "page1_rows" in rep and not (isinstance(rep["page1_rows"], int) and 3 <= rep["page1_rows"] <= 5): errs.append("page1_rows must be an integer from 3 to 5")
    for path, lim in PAGE1_LIMITS.items():
        cur = rep
        for k in path.split("."): cur = cur.get(k) if isinstance(cur, dict) else None
        n = len(cur) if isinstance(cur, str) else 0
        if n > lim: errs.append(f"{path} is {n} chars; page-1 budget allows {lim}")
    return errs


def _bridge_rows(model):
    """The bridge that drives the report: to-market in measured mode (ranked by revenue), market→founder otherwise."""
    if model.get("mode") == "measured":
        return (model["combined"]["bridge_to_market"] if "lines" in model else model["bridge_to_market"]), "revenue_end"
    return (model["combined"]["bridge"] if "lines" in model else model["bridge"]), "peak_capital_need"


def top_bridge_domains(model, rep, k=TOP_STORIES):
    """(line, domain) of the k bridge rows with the largest effect across lines (zero-effect rows excluded)."""
    src, key = _bridge_rows(model)
    rows = [((b.get("line") if "lines" in model else None), b["domain"], abs((b.get(key) or {}).get("delta") or 0)) for b in src]
    rows = [x for x in rows if x[2] > 0 and "+" not in x[1] and x[1] not in COST_DOMAINS]
    if not rows:   # every row has zero effect on the ranking key: fall back to the other outcome so the report still tells the stories
        other = "revenue_end" if key == "peak_capital_need" else "peak_capital_need"
        rows = [((b.get("line") if "lines" in model else None), b["domain"], abs((b.get(other) or {}).get("delta") or 0)) for b in src if "+" not in b["domain"]]
    rows.sort(key=lambda x: -x[2])
    out = rows[:k]
    if len(rows) > k:   # ties at the boundary are all required
        out += [x for x in rows[k:] if x[2] == rows[k - 1][2]]
    return [(ln, d) for ln, d, _ in out]


def _txt(x): return str(x or "").strip()


def check_requirements(rep, model, charts_dir, T):
    errs = []
    if rep.get("verdict") not in VERDICTS: errs.append(f"verdict must be one of {VERDICTS}, got {rep.get('verdict')!r}")
    has_number = lambda s: bool(re.search(r"\d|\{\{", s or ""))
    # verdict rule that the builder can check: a category estimate (half or more of the rows carry no team number) cannot be assessed
    cnt = model.get("counts") or (next(iter(model["lines"].values()))["counts"] if "lines" in model else {})
    if cnt.get("category_estimate") and rep.get("verdict") != "Not assessable":
        errs.append("verdict must be 'Not assessable': half or more of the assumptions carry no team number (counts.category_estimate) — the report describes a category, not this business; ask for the team's numbers first")
    if rep.get("verdict") in ("Proceed with conditions", "Not assessable"):
        conds = rep.get("conditions") or []
        if not (isinstance(conds, list) and 2 <= len(conds) <= 4 and all(_txt(x) and len(str(x)) <= 140 for x in conds)):
            errs.append("conditions: 2–4 short lines (≤ 140 chars) are required for this verdict — what has to happen (or what data is needed) before the business can be assessed as viable")
        for i, x in enumerate(conds if isinstance(conds, list) else []):
            if not has_number(x) and not PLACEHOLDER.search(str(x)): errs.append(f"conditions[{i}] must carry a number or a placeholder — a condition without a threshold cannot be checked")
    kc = rep.get("kill_criterion")
    if kc is not None:
        if not (isinstance(kc, dict) and all(_txt(kc.get(f)) for f in ("metric", "threshold", "what_model_shows"))): errs.append("kill_criterion needs metric, threshold and what_model_shows")
        elif not has_number(kc["threshold"]): errs.append("kill_criterion.threshold must be a number")
    for k in ("startup", "verdict_text", "evidence_basis"):
        if not _txt(rep.get(k)): errs.append(f"missing {k}")
    try:
        cases, br, cmp_, n, comb, name = lead(model, rep)
    except ValueError as e:
        return [str(e)]
    st = rep.get("story")
    if not (isinstance(st, list) and len(st) == 5 and all(not _short(x, MIN_LEN["story_sentence"]) for x in st)): errs.append(f"story must be exactly five sentences of at least {MIN_LEN['story_sentence']} characters each")
    elif sum(len(x) for x in st) > STORY_LIMIT: errs.append(f"story is {sum(len(x) for x in st)} chars; page-1 budget allows {STORY_LIMIT}")
    all_lines = model["lines"].items() if comb else [(None, {"cases": cases, "comparison": cmp_, "bridge": br})]
    for ln, r in all_lines:
        tag = f" (line {ln})" if ln else ""
        if not (r["cases"]["market"]["growth"].get("funnel") or []): errs.append(f"growth.funnel is empty{tag}")
        for row in r["comparison"]:
            if row["fill"] != "unverified" and not _txt(row.get("source")): errs.append(f"comparison row {row['domain']!r}{tag} has no market source")
        if not r["bridge"] and not any(row["status"] == "observed" for row in r["comparison"]):
            errs.append(f"no assumption differs between founder and market{tag} and nothing is measured — nothing to compare")
    # assumption stories: the top bridge domains must each have a story with all four parts
    A_ = rep.get("assumptions") or {}
    if not _txt(A_.get("lead")): errs.append("assumptions.lead is required (one sentence: which assumptions decide the case)")
    stories = A_.get("stories") or []
    have = {(s_.get("line") if comb else None, s_.get("domain")) for s_ in stories}
    known = {(ln, c_["domain"]) for ln, r in all_lines for c_ in r["comparison"]} | {(ln, b["domain"]) for ln, r in all_lines for b in r["bridge"]}
    for i, s_ in enumerate(stories):
        for k in ("belief", "evidence", "stakes", "test"):
            if _short(s_.get(k), MIN_LEN["story_part"]): errs.append(f"assumptions.stories[{i}].{k} must be at least {MIN_LEN['story_part']} characters")
        if not has_number(s_.get("stakes")): errs.append(f"assumptions.stories[{i}].stakes must quote what it is worth (a placeholder into bridge.*)")
        if not has_number(s_.get("test")): errs.append(f"assumptions.stories[{i}].test must carry a numeric threshold")
        if comb and s_.get("line") not in model["lines"]: errs.append(f"assumptions.stories[{i}]: line {s_.get('line')!r} not in model")
        elif ((s_.get("line") if comb else None), s_.get("domain")) not in known: errs.append(f"assumptions.stories[{i}]: domain {s_.get('domain')!r} is not in the model's comparison")
    for ln, d in top_bridge_domains(model, rep):
        if (ln, d) not in have: errs.append(f"assumptions.stories must cover {d!r}{' (line ' + ln + ')' if ln else ''} — one of the {TOP_STORIES} assumptions with the largest effect on capital need")
    for sec in ("market_case", "founder_case", "competition"):
        o = rep.get(sec) or {}
        if _short(o.get("lead"), MIN_LEN["lead"]): errs.append(f"{sec}.lead must be a sentence of at least {MIN_LEN['lead']} characters")
        ps = [p for p in (o.get("paragraphs") or []) if _txt(p)]
        if not ps: errs.append(f"{sec}.paragraphs needs at least one paragraph")
        for j, p in enumerate(ps):
            if _short(p, MIN_LEN["paragraph"]): errs.append(f"{sec}.paragraphs[{j}] must be at least {MIN_LEN['paragraph']} characters")
    if _short(A_.get("lead"), MIN_LEN["lead"]): errs.append(f"assumptions.lead must be at least {MIN_LEN['lead']} characters")
    cp = rep.get("competition") or {}
    dims = cp.get("dimensions") or []
    if not (2 <= len(dims) <= 3): errs.append(f"competition.dimensions needs 2–3 features that define the segment, got {len(dims)}")
    for i, dm in enumerate(dims):
        if not _txt(dm.get("key")) or not _txt(dm.get("label")) or _short(dm.get("why"), MIN_LEN["lead"]): errs.append(f"competition.dimensions[{i}] needs key, label and a 'why' sentence (≥ {MIN_LEN['lead']} chars)")
    dkeys = [dm.get("key") for dm in dims]
    rows = cp.get("rows") or []
    if len(rows) < 5: errs.append(f"competition.rows needs at least five products (the startup plus competitors), got {len(rows)}")
    layers = [r_.get("layer") for r_ in rows]
    for lay in ("direct", "indirect", "displacer"):
        if lay not in layers: errs.append(f"competition.rows must include at least one {lay!r} row")
    if sum(1 for r_ in rows if r_.get("self")) != 1: errs.append("competition.rows must mark exactly one row as the startup itself (self: true)")
    for i, r_ in enumerate(rows):
        if r_.get("layer") not in ("direct", "indirect", "displacer"): errs.append(f"competition.rows[{i}].layer must be direct / indirect / displacer")
        for f in ("name", "price", "source"):
            if not _txt(r_.get(f)): errs.append(f"competition.rows[{i}] needs {f}")
        for k_ in dkeys:
            if not _txt((r_.get("cells") or {}).get(k_)): errs.append(f"competition.rows[{i}] ({r_.get('name')}) has no cell for dimension {k_!r} — write 'no' / 'unknown' rather than leave it out")
        for k_ in (r_.get("cells") or {}):
            if k_ not in dkeys: errs.append(f"competition.rows[{i}] has a cell {k_!r} that is not a declared dimension")
    if not _txt(cp.get("where_we_win")): errs.append("competition.where_we_win is required")
    nx = rep.get("next_90_days") or []
    if not (3 <= len(nx) <= 5): errs.append(f"next_90_days needs 3–5 items, got {len(nx)}")
    nx_domains = []
    for i, x in enumerate(nx):
        for k in ("title", "what", "how", "threshold", "domain"):
            if not _txt(x.get(k)): errs.append(f"next_90_days[{i}] needs {k}" + (" — the assumption it tests, or 'other'" if k == "domain" else ""))
        if _short(x.get("threshold"), MIN_LEN["threshold"]) or not has_number(x.get("threshold")): errs.append(f"next_90_days[{i}].threshold must state a number and a time")
        nx_domains.append(x.get("domain"))
    top_t = [t for t in (model.get("tornado") or (next(iter(model["lines"].values()))["tornado"] if "lines" in model else [])) if t["fill"] == "filled_from_market" and t["domain"] not in ("fte_cost",)]
    if top_t and top_t[0]["width_capital"] > 0 and top_t[0]["domain"] not in nx_domains:
        errs.append(f"next_90_days must include a test for {top_t[0]['domain']!r} — the team gave no number for it and it is the market assumption the outcome depends on most (tornado)")
    top1 = top_bridge_domains(model, rep, k=1)
    if top1 and top1[0][1] not in nx_domains: errs.append(f"next_90_days must include a test for {top1[0][1]!r} — the assumption with the largest effect on capital need")
    for ln, r in all_lines:
        for c_ in r["comparison"]:
            if c_["fill"] == "unverified" and c_["domain"] not in nx_domains: errs.append(f"next_90_days must include a test for {c_['domain']!r}{' (line ' + ln + ')' if ln else ''} — it has no market data")
    rk = rep.get("risks") or []
    if len(rk) < 2: errs.append("risks needs at least two items")
    for i, x in enumerate(rk):
        if not _txt(x.get("title")): errs.append(f"risks[{i}] needs a title")
        for f, n in (("what", MIN_LEN["risk_part"]), ("impact", MIN_LEN["risk_part"]), ("signal", MIN_LEN["risk_signal"]), ("action", MIN_LEN["risk_signal"])):
            if _short(x.get(f), n): errs.append(f"risks[{i}].{f} must be at least {n} characters — the event, what it does to the numbers, a measurable early sign, the action")
        if not has_number(x.get("impact")) and not PLACEHOLDER.search(str(x.get("impact") or "")): errs.append(f"risks[{i}].impact must say what happens to the numbers — a placeholder into the model or a number")
        if not has_number(x.get("signal")): errs.append(f"risks[{i}].signal must be measurable — a number and a time")
        if x.get("likelihood") not in ("High", "Medium", "Low"): errs.append(f"risks[{i}].likelihood must be High / Medium / Low")
        if x.get("reversibility") not in ("Reversible", "Structural", "Unknown"): errs.append(f"risks[{i}].reversibility must be Reversible / Structural / Unknown")

    ap = rep.get("appendix") or {}
    if not (isinstance(ap.get("evidence"), list) and len(ap["evidence"]) >= 2): errs.append("appendix.evidence needs a header row and at least one data row")
    kp = rep.get("kpis") or []
    if kp and not (3 <= len(kp) <= 6): errs.append("kpis: 3–6 tiles")
    for k in kp:
        refs = k.get("pair") or [k.get("ref")]
        if not _txt(k.get("label")): errs.append("kpi without label")
        if k.get("fmt", "text") not in FORMATS: errs.append(f"kpi {k.get('label')!r}: unknown fmt {k.get('fmt')!r}")
        for r in refs:
            if not r: errs.append(f"kpi {k.get('label')!r}: needs ref or pair"); continue
            try:
                get_ref(model, r)
                val = get_ref(model, r); kind = "str" if isinstance(val, str) else field_kind(r, model)
                if k.get("fmt", "text") not in COMPATIBLE.get(kind, set(FORMATS)): errs.append(f"kpi {k.get('label')!r}: fmt {k.get('fmt')!r} does not fit {r}")
            except KeyError as e: errs.append(f"kpi {k.get('label')!r}: {e}")
    errs += check_page1_budget(rep) + check_labels(rep, T) + check_charts(charts_dir, model, rep)
    return errs


def verify_pagination(docx_path, T):
    import shutil, subprocess, tempfile, pathlib
    if not shutil.which("pdftotext"): return None, "pagination not verified: pdftotext not available"
    if not docx_path.lower().endswith(".pdf") and not shutil.which("soffice"): return None, "pagination not verified: soffice not available"
    with tempfile.TemporaryDirectory() as d:
        if docx_path.lower().endswith(".pdf"):
            pdf = docx_path
        else:
            from recalc import soffice_env
            subprocess.run(["soffice", "--headless", f"-env:UserInstallation={pathlib.Path(d, 'p').as_uri()}", "--convert-to", "pdf", "--outdir", d, docx_path],
                           capture_output=True, text=True, timeout=240, env=soffice_env())
            pdf = os.path.join(d, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        if not os.path.exists(pdf): return None, "pagination not verified: PDF conversion failed"
        def lines(n):
            txt = subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), "-layout", pdf, "-"], capture_output=True, text=True).stdout
            return [re.sub(r"\s+", " ", x).strip() for x in txt.splitlines()]
        p1, p2, p3 = lines(1), lines(2), lines(3)
        heading = lambda pg, t: any(x == t for x in pg)   # a heading is a whole line, not a substring inside prose
        ok = heading(p1, T["comparison"]) and heading(p2, T["dashboard"]) and not heading(p1, T["dashboard"]) and heading(p3, T["assumptions"])
        return ok, ("pagination verified: comparison on page 1, dashboard on page 2, assumptions open page 3" if ok else
                    f"pagination FAILED: page 1 has comparison heading = {heading(p1, T['comparison'])}, page 2 has dashboard heading = {heading(p2, T['dashboard'])}, page 3 opens with the assumptions = {heading(p3, T['assumptions'])} (a dashboard note spilling onto its own page is the usual cause)")


# ── build ────────────────────────────────────────────────────

def fail(msg, lines=()):
    print("ERROR: " + msg, file=sys.stderr)
    for l in lines: print("  - " + str(l), file=sys.stderr)
    sys.exit(2)


def build(rep, charts_dir, out_path, model=None, strict=False):
    if model is None: fail("--model <model.json> is required; every numeric table is generated from it.")
    lang = str(rep.get("lang", "en")).lower()
    if lang not in LABELS: fail(f"lang {rep.get('lang')!r} not supported; use one of {sorted(LABELS)}")
    T = dict(LABELS[lang]); cur = str(rep.get("currency", "$"))
    chart_style.DEC = "," if lang == "ru" else "."   # decimal separator follows the report language everywhere (prose, tables, charts)
    global MFMT; MFMT = T.get("mfmt", "M{v}"); chart_style.MFMT = MFMT
    if model.get("mode") == "measured": T.update(T["_measured"])   # a live business is read as "where you stand", not "if the team is right"
    errs = check_schema(rep) + check_labels(rep, T)
    if errs: fail("report.json is malformed:", errs)
    T.update(rep.get("labels", {}))
    errs = check_placeholders(rep, model) + check_story_bindings(rep, model)
    if errs: fail("placeholders:", errs)
    try:
        bad = verify_free_text(rep)
    except ValueError as e:
        fail(str(e))
    if bad: fail(f"{len(bad)} number(s) in the report text are neither {{{{ref|fmt}}}} placeholders nor declared manual numbers:", [f"[{w}] {t!r} in …{c}…" for w, t, c in bad[:40]])
    raw_verdict = str(rep.get("verdict_text", ""))
    rep = render_placeholders(rep, model, cur, T)
    errs = check_rendered(rep) + check_requirements(rep, model, charts_dir, T)
    if len(str(rep.get("verdict_text", ""))) > 480: errs.append(f"verdict_text renders to {len(rep['verdict_text'])} chars; page-1 budget allows 480 rendered (320 raw) — the funding-path placeholder expands to a sentence, do not repeat it in your own words")
    if "capital_vs_round.position" not in raw_verdict:
        errs.append("verdict_text must carry the funding-path line: {{capital_vs_round.position|text}} (market-case capital need against the typical round for the stated funding path)")
    if errs: fail(f"report.json does not meet the report requirements ({len(errs)}):", errs)
    hits = lint_register(rep)
    if hits:
        print(f"REGISTER WARNINGS ({len(hits)}): the report reads like a chat turn in these places — rewrite before delivering:", file=sys.stderr)
        for path, label, snip in hits[:40]: print(f"  [{label}] {path}: …{snip}…", file=sys.stderr)
        if strict: sys.exit(2)

    cases, br, cmp_rows, n, comb, lname = lead(model, rep); T["_n"] = n
    if out_path.lower().endswith(".html"):   # the interactive page: same verified content, screen stylesheet, one self-contained file
        from build_pdf import render_html
        with open(out_path, "w", encoding="utf-8") as f: f.write(render_html(rep, T, cur, model, charts_dir, screen=True))
        print("html written (not paginated; build the .pdf from the same report.json for print)", file=sys.stderr); print(out_path); return
    if out_path.lower().endswith(".pdf"):   # same verified content, rendered as a designed PDF (HTML + WeasyPrint)
        from build_pdf import render_pdf
        render_pdf(rep, T, cur, model, charts_dir, out_path)
        ok, msg = verify_pagination(out_path, T)
        if ok is False:
            failed = os.path.splitext(out_path)[0] + ".FAILED.pdf"; os.replace(out_path, failed)
            fail(msg + f" — kept as {failed} for inspection; page 1 is over budget: shorten the story / verdict, set page1_rows: 4 or 3, or drop kill_criterion")
        print(msg if ok else "WARNING: " + msg, file=sys.stderr)
        if ok is None and strict: os.remove(out_path); sys.exit(2)
        print(out_path); return
    if not HAVE_DOCX: fail("python-docx is not installed — build the .html or .pdf instead, or `pip install python-docx`")
    doc = Document(); st = doc.styles["Normal"]; st.font.name = "Arial"; st.font.size = Pt(10.5)
    for s_ in doc.sections: s_.left_margin = s_.right_margin = Cm(2); s_.top_margin = s_.bottom_margin = Cm(1.8)
    lines_iter = list(model["lines"].items()) if comb else [(None, model)]

    # ── page 1: title, verdict, the story, tiles, the one table
    p = doc.add_paragraph(); r = p.add_run(rep["startup"]); r.font.size = Pt(24); r.bold = True; r.font.color.rgb = NAVY; r.font.name = "Arial"; p.paragraph_format.space_after = Pt(0)
    para(doc, f"{T['title_suffix']} · {rep.get('date', '')}", size=11, color=GREY, after=2)
    para(doc, T["scope_note"], size=9, italic=True, color=GREY, after=8)
    vt = doc.add_table(rows=1, cols=1); vt.alignment = WD_TABLE_ALIGNMENT.CENTER; c = vt.cell(0, 0); shade(c, VERDICT_COLORS[rep["verdict"]]); c.text = ""
    p = c.paragraphs[0]; r = p.add_run(T["verdict_names"][rep["verdict"]]); r.bold = True; r.font.size = Pt(16); r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); r.font.name = "Arial"
    p2 = c.add_paragraph(); r2 = p2.add_run(rep["verdict_text"]); r2.font.size = Pt(10.5); r2.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); r2.font.name = "Arial"
    if rep.get("conditions"):
        p3 = c.add_paragraph(); r3 = p3.add_run((T["need_k"] if rep["verdict"] == "Not assessable" else T["cond_k"]) + ": " + " · ".join(rep["conditions"])); r3.font.size = Pt(9.5); r3.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); r3.font.name = "Arial"
    for pp in c.paragraphs: pp.paragraph_format.space_after = Pt(4)
    h(doc, T["story"], 2)
    for i, sent in enumerate(rep["story"], 1):
        p = doc.add_paragraph(); r = p.add_run(f"{i}  "); r.bold = True; r.font.color.rgb = NAVY; r.font.name = "Arial"; r.font.size = Pt(10.5)
        r2 = p.add_run(sent); r2.font.name = "Arial"; r2.font.size = Pt(10.5); p.paragraph_format.space_after = Pt(2)
    eb = doc.add_paragraph(); rr = eb.add_run(T["evidence_basis"] + ": "); rr.bold = True; rr.font.size = Pt(9); rr.font.name = "Arial"
    r2 = eb.add_run(rep["evidence_basis"]); r2.font.size = Pt(9); r2.font.name = "Arial"; r2.font.color.rgb = GREY; eb.paragraph_format.space_before = Pt(4); eb.paragraph_format.space_after = Pt(6)
    kpis = rep.get("kpis") or default_kpis(model, rep, T)
    kt = doc.add_table(rows=2, cols=len(kpis)); kt.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, k in enumerate(kpis):
        set_cell(kt.cell(0, j), kpi_value(k, model, cur, T), bold=True, size=11, color=NAVY, align=WD_ALIGN_PARAGRAPH.CENTER)
        set_cell(kt.cell(1, j), k["label"], size=7, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER); shade(kt.cell(0, j), "F2F4F8"); shade(kt.cell(1, j), "F2F4F8")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    h(doc, T["comparison"], 2)
    notes = (rep.get("comparison") or {}).get("notes") or {}
    all_rows = []
    measured = model.get("mode") == "measured"
    src_rows, key_ = _bridge_rows(model)
    rank = {(x["line"], x["domain"]): x[key_]["delta"] for x in src_rows} if comb else None
    for ln, r_ in lines_iter: all_rows += gen_comparison(r_["comparison"], (r_["bridge_to_market"] if measured else r_["bridge"]), T, cur, notes, line=ln, rank=rank, measured=measured)
    all_rows.sort(key=lambda x: -x[5]); all_rows = [x[:5] for x in all_rows]
    n1 = page1_rows(rep)
    table(doc, [T["cmp_hdr"]] + all_rows[:n1], [3.0, 2.6, 4.6, 1.1, 5.7], font_size=7.5)
    if len(all_rows) > n1: para(doc, T["cmp_more"].format(n=len(all_rows) - n1), size=8.5, italic=True, color=GREY, after=2)

    # ── page 2: dashboard
    sec = doc.add_section(WD_SECTION.NEW_PAGE); sec.orientation = WD_ORIENT.LANDSCAPE; sec.page_width, sec.page_height = sec.page_height, sec.page_width
    sec.left_margin = sec.right_margin = Cm(1.5); sec.top_margin = sec.bottom_margin = Cm(1.2)
    h(doc, T["dashboard"])
    doc.add_picture(os.path.join(charts_dir, "dashboard.png"), width=Cm(22.5)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(doc, T["dashboard_note"], size=8.5, italic=True, color=GREY)
    sec2 = doc.add_section(WD_SECTION.NEW_PAGE); sec2.orientation = WD_ORIENT.PORTRAIT; sec2.page_width, sec2.page_height = sec2.page_height, sec2.page_width
    sec2.left_margin = sec2.right_margin = Cm(2); sec2.top_margin = sec2.bottom_margin = Cm(1.8)

    # ── what the team believes and what the market shows
    h(doc, T["assumptions"]); lead_para(doc, rep["assumptions"]["lead"])
    if "bridge.png" in required_charts(model, rep)["dashboard.json"]:   # only an image this build required and verified; never a leftover
        doc.add_picture(os.path.join(charts_dir, "bridge.png"), width=Cm(16)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    bridge_ix = {}
    for ln, r_ in lines_iter:
        for b in r_["bridge"]: bridge_ix[(ln, b["domain"])] = b
    cmp_ix = {}
    for ln, r_ in lines_iter:
        for c_ in r_["comparison"]: cmp_ix[(ln, c_["domain"])] = c_
    top = top_bridge_domains(model, rep, k=99)
    order = {key: i for i, key in enumerate(top)}
    stories = sorted(rep["assumptions"]["stories"], key=lambda s_: order.get((s_.get("line") if comb else None, s_["domain"]), 999))
    for s_ in stories:
        key = (s_.get("line") if comb else None, s_["domain"]); c_ = cmp_ix.get(key); b = bridge_ix.get(key)
        title = T["dom"].get(s_["domain"], s_["domain"]).capitalize() + (f" — {key[0]}" if key[0] else "")
        h(doc, title, 2)
        if c_:
            para(doc, T["vs"].format(f=_dv(c_["kind"], c_["founder"], cur), m=_dv(c_["kind"], c_["market"], cur) + (f" [{_dv(c_['kind'], c_['market_low'], cur)}–{_dv(c_['kind'], c_['market_high'], cur)}]" if c_["market_low"] != c_["market_high"] else "")), size=10, color=GREY, after=4)
        labelled(doc, T["st_believes"], s_["belief"]); labelled(doc, T["st_evidence"], s_["evidence"]); labelled(doc, T["st_stakes"], s_["stakes"]); labelled(doc, T["st_test"], s_["test"])

    # ── the business on the market's numbers
    h(doc, T["market_case"]); lead_para(doc, rep["market_case"]["lead"])
    for p_ in rep["market_case"]["paragraphs"]: para(doc, p_)
    doc.add_picture(os.path.join(charts_dir, "chart_mrr.png"), width=Cm(15)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    rows = gen_outcomes(model, rep, T, cur); table(doc, [[rows[0][0], T["market"], T["market_range"]]] + [[r[0], r[2], f"{r[3]} / {r[4]}"] for r in rows[1:]], [7, 4, 6], font_size=8.5)
    para(doc, T["market_range_note"], size=8.5, italic=True, color=GREY)

    # ── if the team is right
    h(doc, T["founder_case"]); lead_para(doc, rep["founder_case"]["lead"])
    for p_ in rep["founder_case"]["paragraphs"]: para(doc, p_)
    for ln, r_ in lines_iter:
        ue = gen_unit_economics(r_["cases"], T, cur, (f"{T['line']}: {ln}" if ln else r_["cases"]["market"]["inputs"]["revenue_unit"]))
        table(doc, [[ue[0][0], T["founder"], T["market"]]] + [[r[0], r[1], r[2]] for r in ue[1:]], [8, 4.5, 4.5], font_size=8.5)

    # ── competition
    h(doc, T["competition"]); lead_para(doc, rep["competition"]["lead"]); cp = rep["competition"]
    dims = cp["dimensions"]
    p = doc.add_paragraph(); r = p.add_run(T["dims_intro"] + ". "); r.bold = True; r.font.name = "Arial"; r.font.size = Pt(10.5)
    r2 = p.add_run(" ".join(f"{dm['label']} — {dm['why']}" for dm in dims)); r2.font.name = "Arial"; r2.font.size = Pt(10.5); p.paragraph_format.space_after = Pt(6)
    hdr = [T["col_product"], T["col_layer"], T["col_price"]] + [dm["label"] for dm in dims] + [T["col_source"]]
    rows_c = [hdr]
    for r_ in sorted(cp["rows"], key=lambda x: (not x.get("self"), ("direct", "indirect", "displacer").index(x["layer"]))):
        rows_c.append([r_["name"] + (f" ({T['self_mark']})" if r_.get("self") else ""), T["layer_short"][r_["layer"]], r_["price"]] + [r_["cells"][dm["key"]] for dm in dims] + [r_["source"]])
    ndim = len(dims); wd = [3.0, 1.8, 2.2] + [round((17.0 - 3.0 - 1.8 - 2.2 - 2.6) / ndim, 1)] * ndim + [2.6]
    t = table(doc, rows_c, wd, font_size=7.5)
    for i, r_ in enumerate(rows_c[1:], 1):
        if r_[0].endswith(f"({T['self_mark']})"):
            for c in t.rows[i].cells:
                shade(c, "FFF4E0")
                for pp in c.paragraphs:
                    for rr in pp.runs: rr.bold = True
    for p_ in cp["paragraphs"]: para(doc, p_)
    labelled(doc, T["where_we_win"], cp["where_we_win"])

    # ── next 90 days
    h(doc, T["next_90"])
    for i, x in enumerate(rep["next_90_days"], 1):
        p = doc.add_paragraph(); r = p.add_run(f"{i}. {x['title']}"); r.bold = True; r.font.name = "Arial"; r.font.size = Pt(11); r.font.color.rgb = NAVY; p.paragraph_format.space_after = Pt(2)
        para(doc, x["what"], after=2); para(doc, x["how"], after=2)
        p = doc.add_paragraph(); r = p.add_run(T["col_threshold"] + ": "); r.bold = True; r.font.name = "Arial"; r.font.size = Pt(10.5)
        r2 = p.add_run(x["threshold"]); r2.font.name = "Arial"; r2.font.size = Pt(10.5); p.paragraph_format.space_after = Pt(8)

    # ── risks
    h(doc, T["risks_h"]); para(doc, T["risks_intro"], size=9.5, italic=True, color=GREY)
    rows_r = [[T["col_risk"], T["col_likelihood"] + " / " + T["col_reversibility"], T["col_what_happens"], T["col_signal"], T["col_action"]]]
    for x in rep["risks"]:
        rows_r.append([x["title"] + ". " + x["what"], T["risk_enum"][x["likelihood"]] + " / " + T["risk_enum"][x["reversibility"]], x["impact"], x["signal"], x["action"]])
    t = table(doc, rows_r, [4.2, 2.0, 3.8, 3.4, 3.6], font_size=8)
    for i, x in enumerate(rep["risks"], 1):
        c = t.rows[i].cells[0]; c.text = ""; pp = c.paragraphs[0]
        rr = pp.add_run(x["title"] + ". "); rr.bold = True; rr.font.size = Pt(8); rr.font.name = "Arial"
        rr = pp.add_run(x["what"]); rr.font.size = Pt(8); rr.font.name = "Arial"; pp.paragraph_format.space_after = Pt(2)

    # ── appendix: the exhibits
    doc.add_page_break(); h(doc, T["appendix"])
    h(doc, T["ap_assumptions"], 2)
    for ln, r_ in lines_iter:
        if ln: para(doc, f"{T['line']}: {ln}", size=10, color=GREY, after=2)
        rows_a = [[T["cmp_hdr"][0], T["cmp_hdr"][1], T["cmp_hdr"][2], T["cmp_hdr"][3]]]
        for c_ in r_["comparison"]:
            stt = T["status"].get(c_["status"], c_["status"]); fl = T["fill"].get(c_["fill"], "") if c_["fill"] else ""
            mk = _dv(c_["kind"], c_["market"], cur) + (f" [{_dv(c_['kind'], c_['market_low'], cur)}–{_dv(c_['kind'], c_['market_high'], cur)}]" if c_["market_low"] != c_["market_high"] else "")
            rows_a.append([T["dom"].get(c_["domain"], c_["label"]), f"{_dv(c_['kind'], c_['founder'], cur)} ({stt}{'; ' + fl if fl else ''})", f"{mk} · {c_['source'] or T['fill']['unverified']}", "—" if c_["gap_ratio"] is None else ("∞" if isinstance(c_["gap_ratio"], str) else fmt_mult(c_["gap_ratio"]))])
        table(doc, rows_a, [3.6, 3.4, 8.6, 1.4], font_size=8)
    h(doc, T["ap_evidence"], 2); table(doc, rep["appendix"]["evidence"], None, font_size=8)
    h(doc, T["ap_cases"], 2); table(doc, gen_outcomes(model, rep, T, cur), [6, 2.75, 2.75, 2.75, 2.75], font_size=8)
    for fname in ("chart_cash.png", "chart_customers.png"):
        doc.add_picture(os.path.join(charts_dir, fname), width=Cm(15)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    h(doc, T["ap_ue"], 2)
    for ln, r_ in lines_iter:
        table(doc, gen_unit_economics(r_["cases"], T, cur, (f"{T['line']}: {ln} ({r_['cases']['market']['inputs']['revenue_unit']})" if ln else r_["cases"]["market"]["inputs"]["revenue_unit"])), [6, 2.75, 2.75, 2.75, 2.75], font_size=8)
    h(doc, T["ap_funnel"], 2)
    for ln, r_ in lines_iter:
        gtext, funnel, cap = gen_growth(r_["cases"], r_["comparison"], T)
        para(doc, (f"{T['line']}: {ln} · " if ln else "") + gtext, size=9.5, color=GREY, after=4)
        if len(funnel) > 1: table(doc, funnel, [6, 3.5, 7.5], font_size=8)
        para(doc, cap, size=9.5)
    for ln, r_ in lines_iter:
        cb = gen_comparable(r_["cases"], T, cur)
        if cb: h(doc, T["ap_comparable"] + (f" — {ln}" if ln else ""), 2); table(doc, cb, [6, 2.75, 2.75, 2.75, 2.75], font_size=8)
    h(doc, T["ap_bridge"], 2)
    for ln, r_ in lines_iter:
        if r_["bridge"]:
            if ln: para(doc, f"{T['line']}: {ln}", size=9.5, color=GREY, after=2)
            table(doc, gen_bridge(r_["bridge"], T, cur, n), [3.2, 2.4, 2.8, 2.0, 2.8, 2.0, 1.8], font_size=8)
    if model.get("mode") == "measured":
        para(doc, T["_measured"]["bridge_intro"], size=9.5, color=GREY, after=2)
        for ln, r_ in lines_iter:
            btm = r_.get("bridge_to_market") or []
            if btm:
                if ln: para(doc, f"{T['line']}: {ln}", size=9.5, color=GREY, after=2)
                be = lambda v: mlabel(v) if v else T["none"]
                rows_m = [[T["cmp_hdr"][0], T["bridge_hdr"][1].replace("→", "→"), T["bridge_hdr"][4].replace("{n}", str(n)), T["bridge_hdr"][2], T["bridge_hdr"][3]]]
                for x in btm:
                    rows_m.append([T["dom"].get(x["domain"], x["label"]), f"{_dv(x['kind'], x['measured'], cur)} → {_dv(x['kind'], x['category'], cur)}", f"{money(x['revenue_end']['measured'], cur)} → {money(x['revenue_end']['if_at_category'], cur)}",
                                   f"{money(x['peak_capital_need']['measured'], cur)} → {money(x['peak_capital_need']['if_at_category'], cur)}", f"{be(x['breakeven_month']['measured'])} → {be(x['breakeven_month']['if_at_category'])}"])
                table(doc, rows_m, [3.6, 3, 3.6, 3.6, 3.2], font_size=8)
    if comb and comb.get("bridge"):
        para(doc, T["ap_bridge_comb"], size=9.5, color=GREY, after=2)
        rows_c = [[T["line"], T["cmp_hdr"][0], T["bridge_hdr"][1], T["bridge_hdr"][2], T["bridge_hdr"][3]]]
        for x in comb["bridge"]:
            be = lambda v: mlabel(v) if v else T["none"]
            rows_c.append([x["line"], T["dom"].get(x["domain"], x["label"]), ("—" if x["kind"] == "joint" else f"{_dv(x['kind'], x['market'], cur)} → {_dv(x['kind'], x['founder'], cur)}"),
                           f"{money(x['peak_capital_need']['market'], cur)} → {money(x['peak_capital_need']['if_founder_right'], cur)}", f"{be(x['breakeven_month']['market'])} → {be(x['breakeven_month']['if_founder_right'])}"])
        table(doc, rows_c, [2.5, 4, 3, 4, 3.5], font_size=8)
    para(doc, T["model_note"], size=9, italic=True, color=GREY)
    doc.save(out_path)
    ok, msg = verify_pagination(out_path, T)
    if ok is False:
        os.remove(out_path); fail(msg + " — the document was not kept")
    if ok is None:
        print("WARNING: " + msg, file=sys.stderr)
        if strict: os.remove(out_path); sys.exit(2)
    else:
        print(msg, file=sys.stderr)
    print(out_path)


if __name__ == "__main__":
    if len(sys.argv) < 4: print(__doc__); sys.exit(1)
    model = json.load(open(sys.argv[sys.argv.index("--model") + 1])) if "--model" in sys.argv else None
    build(json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3], model, strict="--strict" in sys.argv)
