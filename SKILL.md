---
name: startup-viability-check
description: Stress-test a startup idea end to end — screening, research (direct, indirect and displacer competitors), calibrated ranges, a deterministic financial model with an Excel workbook, and a viability report. Use when a user asks whether an idea is viable, wants to validate or pressure-test a startup, needs unit economics or projections for an early venture, or a pitch-deck sanity check; also on "проверь идею", "оцени стартап", "посчитай юнит-экономику".
---

# Startup Viability Check

A two-pass validation pipeline. Pass 1 screens the idea in one short round and decides whether there is anything to model. Pass 2 — research, calibration, a deterministic financial model, and a document-grade report — runs only for cases that pass screening. The discipline that makes the output trustworthy: every number carries its origin (measured / founder-stated / founder-guess; market values carry their source or are flagged unverified), founder claims are never promoted to evidence, and the math is done by scripts so it can be rerun and compared.

What this is for: a founder deciding whether to invest the next three months, a mentor preparing for a session, an early reviewer. What it is not: investment due diligence. The report says so on its title block.

**Language:** answer in the language the user writes in. Field names in artifacts (e.g. `cac_range`) stay in English.

**Tone in chat:** sharp advisor talking to a founder — plain sentences, no jargon, every flagged risk ends with an action. **Tone in the report:** analyst memo, no addressee, no author voice — see `references/report.md` § Register. These are different registers on purpose.

---

## Pass 1 — Screening (always)

Read `references/screening.md`. Ask the six questions in one batch, fill the substitute filter, and return the one-page screening with one of five verdicts. Two rules:

- **The substitute filter decides.** If the buyer gets most of the value from an hour with ChatGPT, a spreadsheet, or a template, and the product's additional value cannot be named, the verdict is "Not modelable — substitute problem". Market size, team, and traction do not override this.
- **Do not make the founder invent a channel.** If the first 10–20 paying customers have no named mechanism, record `channel: undefined` as the primary hypothesis and stop with two 30-day tests. A channel produced under questioning would enter the model as if it were real.

A "Not modelable" screening is a complete deliverable: 2–3 top unknowns, 2–3 cheapest tests with thresholds. Many cases should end here.

**Pass 1b — Reality card.** On "Modelable" / "Modelable with gaps", immediately produce the reality card (`references/screening.md` § Pass 1b): the five load-bearing numbers as the founder's column against `references/benchmarks.json` as the market column, run through `financial_model.py` — the same founder-case / market-case / bridge output the final report is built on, only library-based and unresearched. For a product that already has paying customers the measured numbers are the founder's column (status `observed`) and the card reads as "where you stand". Ten minutes, no web research, library entries cited with tier, date and `verified` flag. This is the first place the founder sees numbers, and for many cases it is enough. Offer Pass 2 as the option to refine with research and comparables — not as the default next step.

---

## Pass 2 — Full assessment

| Step | Name | Output | Gate? |
|---|---|---|---|
| 0 | Intake | Case Card | **user confirms** |
| 1 | Research | Evidence Pack | — |
| 2 | Verification | Verified Evidence Pack | — |
| 3 | Calibration | Assumptions Pack — founder column, market column | **user reviews both columns** (does not upgrade status) |
| 4 | Financial model | founder case · market case · bridge; one .xlsx; charts | — |
| 5 | Report | .docx (+ the .xlsx) | — |

Run 1→2→3 without stopping. The gates exist because a wrong Case Card poisons research and a wrong range poisons the model.

### Step 0 — Intake → Case Card

Read `references/intake.md`. Extract what screening already captured, ask for the rest in one batch. Three things matter most:

1. **Source tags on every number.** `founder_stated` / `founder_guess` / `unknown`. Nothing is `observed` unless the founder shows a measurement (payments, cohorts, ad-platform spend). Founders give points; keep them as points — they are the founder's column. Ranges belong to the market column (benchmark low/high). Never stretch either to swallow a disagreement.
2. **Two axes** (`references/growth.md`): the go-to-market *motion* (what caps new customers) and the *business type* (what a customer is worth). Ask the one driver question for the motion. For a paid motion the driver is the monthly budget, and it is mandatory — CAC will be derived from it.
3. **Revenue unit:** subscription / project / transactional / one_off. This decides the retention math. A product bought once is `one_off` with a repeat rate — not a subscription with 90 % churn.

Present the Case Card as a table and wait for confirmation.

### Step 1 — Research → Evidence Pack

Read `references/research.md`. Start from the library (`references/benchmarks.json`) and try to replace each applicable entry with a fresher or higher-tier source; every fact gets a URL, a tier (`primary` / `survey` / `secondary`), and a date. For direct competitors capture published operating figures — prices, take rates, conversion, customer counts — they become the market column of the Assumptions Pack. Three competitor layers are mandatory — direct, indirect, displacers — each displacer with a defence line. Pull the funnel benchmarks for the case's motion and the comparable benchmark (segment size × comparable penetration — a reference, not a ceiling). Output tables, no narration.

### Step 2 — Verification

Cross the Case Card against the Evidence Pack: `confirmed` / `contradicted` / `unverified` per founder number and per core assumption. Write contradictions bluntly, do not resolve them.

### Step 3 — Calibration → Assumptions Pack

Read `references/calibration.md`. One row per model domain, **two columns that are never merged**: the founder's number with its status (`observed` / `founder_stated` / `founder_guess`) and the market's number or range with its source. No founder number → the row runs on the market value and is flagged; no market evidence → the row runs on the founder's number and is flagged `unverified` and becomes the first experiment. The nearest comparables' actual figures (primary tier) beat category benchmarks for the market column; confidence follows the tier. The gate does not upgrade status: an edited number stays `founder_stated`, and the founder is told so in one line.

### Step 4 — Financial model: the founder's case vs the market's case (scripts, not prose)

Write `input.json` per the schema in the header of `scripts/financial_model.py`: `assumptions{domain: {founder, market, status, source}}` straight from the Assumptions Pack — the market value for the SAME product the founder sells (`unit_of_sale`), derived from a cited library entry or a stated calculation — plus the scalars (growth with a sourced funnel, team, upfront, fixed costs, trial, starting base, comparable benchmark), `funding_path` and `currency` at the top level (plus `fx_rates` when the round benchmark is in another currency), and one block per revenue line (`"lines": [...]`; a team shared by the lines goes in `shared_fixed_monthly`, not in one line's `fte`). Run:

```bash
python scripts/financial_model.py input.json                 # comparison table, four outcomes, bridge; refuses inconsistent inputs
```

What comes out: **four full cases** — `founder` (every domain at the founder's number), `market` (every domain at the market midpoint), `pessimistic` / `optimistic` (the benchmark ranges' edges) — the **comparison** (domain by domain: founder, market, status, source, gap) and the **bridge**: the market case with one assumption at a time set to the founder's number, ranked by the change in capital need. The bridge answers the founder's real question — which of my numbers matters most to prove — from one base, the market case; there is no "everything at mid" anywhere in the method. Bridge rows do not add up (assumptions interact); for several lines the `combined.bridge` re-evaluates every row on total capital need and is what ranks the report. The output also carries `counts` (statuses) and `capital_vs_round` (market-case capital against the typical round for `funding_path`), both meant for placeholders in the prose.

What the scripts enforce: every number must be numeric (a string is refused); acquisition spend = new customers × blended CAC every month; CAC is derived from budget for a paid motion (the domain is then `monthly_budget`); with a channel table the founder's CAC is its volume-weighted average — one number used in the comparison, the cases and the bridge alike (a contradicting founder `cac` is refused), and the market's `cac` drives the market case; `cac` is cash only (zero allowed for purely organic channels; the cash LTV/CAC is then reported as ∞) and unpaid founder hours go into `founder_time_cost_per_customer`, which yields the incl-time ratios without touching the cash flow; LTV uses the same churn and expansion as the projection, capped at 60 months (one-off units likewise); the comparable benchmark is compared at month 36 only and reported as a position, never a diagnosis; zero capacity, zero or reversed ranges, a team without a cost (or a cost without a team), a channel table under a paid motion, a lag longer than the horizon, an unknown motion, a founder value without a status, and a source citing a library entry that does not exist are refused. Read any warning the script prints — it goes into the report.

Two unit caveats the report must carry: for `one_off` lines the "customers" series counts **purchases per month**, not people, and the comparable benchmark is skipped; for multi-line cases the combined customer series **sums units across lines without deduplication**.

`python scripts/selftest.py` runs the regression suite: known-answer checks (cohort math, one-off cap, the four cases, the bridge against a direct run, channel and paid CAC, fills, upfront capital, starting base, horizon), input-validation checks, report-builder checks (placeholders in every key family, number verification, required content, chart manifests, label overrides, lint, rendered pagination), and an internal consistency check that comparison, cases and bridge carry the same numbers, the Excel ↔ Python comparison for every revenue unit across all four cases (including a manual edit of a filled value in the workbook) plus multi-line workbooks (colliding and case-only-different line names) and the Combined sheet. The Excel comparison is mandatory — it uses the bundled `scripts/recalc.py` (needs LibreOffice `soffice` on PATH; it strips cached values and round-trips the file through `soffice --convert-to xlsx`, so every formula is recomputed and charts and formatting survive; no macros; a socket shim is compiled when a sandbox blocks Unix sockets and `gcc` exists; `--recalc <path>` points to another recalculator; `--python-only` skips Excel) and the run exits `INCOMPLETE` if recalculation is unavailable. Only `ALL PASS (python + excel)` is a release-grade result. Run it after any change to the scripts; do not deliver from a build that did not print that line.

**Post-revenue cases:** the measured numbers ARE the founder's column (status `observed`, with source and window) plus `starting_customers` / `starting_mrr`; the market column is the category. **What counts as observed when the founder only talks:** the number of paying customers and the current monthly revenue quoted by the founder of a live business are `observed` (they are facts of the business the founder reads off an invoice list; ask for the export, but do not block on it). Churn, conversion, CAC and volume claims stay `founder_stated` until a cohort table, a CRM count or a spend report is shown — "nobody has churned yet" on six customers over five months is an observation of a small base, and is written as `observed` with the base and window in `source`, so the report can say how thin it is. `observed` on churn or volume together with a starting base puts the model in **measured mode**: base = the business as measured, `bridge_to_market` = what bringing one metric to the category level is worth (ranked by revenue), and the report/dashboard switch to "Where you stand" wording automatically. A live business modelled without a starting base, or with half its rows filled from the market, is labelled by the script as "from zero" / "category estimate" — carry those labels into whatever is delivered. **Horizon:** `months` is an integer 12–120; every "end" figure is labelled with that month.

### Step 5 — Report (a document, not a message)

Fill `report.json` (schema in `scripts/build_report.py`, content guide in `references/report.md`) and run, in this order and from the same input:

```bash
python scripts/check_env.py                                    # what this machine can run; missing LibreOffice / poppler remove a guarantee, not the run
python scripts/lib_audit.py                                    # which library entries are unverified / stale — replace those first in research
python scripts/financial_model.py input.json --json > out/model.json
python scripts/build_workbook.py input.json out/ --name "X" --lang <ru|en> --currency <€|$>            # one .xlsx (four case sheets per line + Combined) + chart PNGs + charts.json
python scripts/recalc.py out/X_financial_model.xlsx                                                   # must report 0 formula errors
python scripts/build_dashboard.py out/model.json out/ --lang <ru|en> --currency <€|$> [--line NAME]   # dashboard.png + bridge.png + dashboard.json
python scripts/number_audit.py report.json out/model.json                                             # every raw number → placeholder or manual_numbers
python scripts/build_report.py report.json out/ out/X_viability_report.html --model out/model.json --strict  # interactive page: one self-contained file (fonts and charts inline), section nav, series toggles, folded appendix
python scripts/build_report.py report.json out/ out/X_viability_report.pdf --model out/model.json --strict   # print of the SAME content (WeasyPrint), paginated and verified; .docx still works
```

**Degraded environments.** `recalc.py` reports `soffice not found` → deliver the workbook anyway and write in the chat summary and the report's model note that its formulas were not recalculated on this machine (the Python numbers stand; the Excel ↔ Python equality is unverified). No `pdftotext` → build the PDF without `--strict` and say the page order was not verified. No `weasyprint` → deliver `.html` (it needs nothing but a browser) and `.docx`. Never silently skip a step. Dependencies: `openpyxl`, `matplotlib`, `python-docx`, `weasyprint` (`pip install openpyxl matplotlib python-docx weasyprint --break-system-packages`), LibreOffice `soffice` for the Excel recalculation, `pdftotext` (poppler) for the pagination check; fonts: Liberation Sans (Arial metrics) with DejaVu fallback. Deliver the HTML and the PDF (same report.json, same checks), the .xlsx, the model input and `report.json`. Page 2 of the PDF / the first section of the HTML is the financial picture: monthly P&L, cumulative cash with the trough annotated as the capital need, the capital waterfall against the typical round, and the signal strip — all inline SVG generated from model.json by `scripts/svg_charts.py`.

The builder **generates** every numeric table from `model.json` — KPI tiles (refs, never literal values), the founder-vs-market comparison, the bridge, unit economics and outcomes for the four cases, the funnel, the comparable benchmark. Numbers in prose — everywhere in `report.json`, including KPI labels, notes, label overrides and appendix cells — are `{{ref|fmt}}` placeholders whose format must fit the field, or entries in `manual_numbers` `{value, field, source, where, context}` bound to the paths and the phrase they appear in (the same value in another wording needs its own entry); a typed number that merely coincides with a model value is rejected, and so is any malformed placeholder. Charts carry manifests with the model fingerprint, PNG hashes and the rendering context (line, language, currency); a stale or replaced image, or a dashboard rendered for another line, fails the build, and only images the current build required are inserted. Required content and page-1 budget are enforced, and after the build the document is rendered to PDF to confirm the comparison table is on page 1 and the dashboard on page 2. With `--strict` the builder also refuses on any register-lint hit. Rewrite and rerun; do not deliver with warnings.

**The report is written, not filled in** (`references/report.md`): a five-sentence story on page 1, then prose sections — "What the team believes and what the market shows" (one four-part story per key assumption: belief, evidence, stakes, test — mandatory for the three assumptions at the top of the bridge), "The business on the market's numbers", "If the team is right", "The competitive picture", "The next 90 days", "Risks". Tables and charts are exhibits the builder adds; the full tables sit in the appendix. Non-negotiables the builder enforces: **page 1 = verdict, story, evidence basis, KPI tiles founder | market, the comparison table; page 2 = the dashboard**; a verdict from exactly three; the funding-path line in the verdict text; a source per funnel step and per market value; 3–5 next-90-days items each with a threshold, the first of them the top bridge assumptions and every `unverified` one; at least two risks with likelihood, reversibility and an action.

**Deliver — always four things:** (1) the report as `.html` (the interactive page) and `.pdf` (the print of the same content — the one that is paginated and verified); (2) **one** model `.xlsx` — Inputs with the founder and market columns as blue cells, four case sheets per line, a formula-driven `Combined` sheet for multi-line cases — so the founder can change either column and watch both cases move; (3) the model input (`input.json`) and `report.json`, so the run can be repeated; (4) in chat, the verdict text and the KPI tiles founder | market. `.docx` is available for anyone who asks. Never deliver the report without the workbook.

---

## Scope — what the model handles well, with caveats, or not at all

| Business | How it is modelled | Caveat |
|---|---|---|
| Subscription SaaS, prosumer or SMB (self-serve or sales-led) | `subscription`: cohort retention, expansion, cash CAC + loaded CAC | sales-led needs `sales_share_of_payroll`, otherwise LTV/CAC is meaninglessly high |
| Services on a monthly retainer (agencies, done-for-you) | `subscription` with `fte` as delivery capacity | capacity does not grow with the book — a hiring step is a founder assumption in the story, not in the model |
| Project-based services, staffing, placements | `project`: value × projects per client-year | repeat frequency is the whole story; make it the first test |
| Marketplaces, transactional platforms | `transactional`: GMV per account × take rate | one-sided: supply is not modelled; liquidity has to be argued in the research, not the model |
| One-off products (reports, tools, D2C) | `one_off` with repeat rate and interval | no inventory or working capital; hardware margins after returns must be in `gross_margin` |
| Enterprise (annual contracts, long cycles) | `subscription` with `sales_cycle_months`, low monthly churn | no prepayment / cash timing; convert annual churn to monthly and say so |
| Ads-funded consumer apps, deep-tech before a unit of sale, non-profits | not modelled | screening stops with a named reason; do not force a unit of sale |

## Verdict rules

The verdict is one of four and the builder checks the first rule: **Not assessable** — half or more of the assumptions carry no team number (`counts.category_estimate`), or a live business gave no starting base; the report then lists what data is needed. **Proceed** — the market case breaks even within the horizon, capital need is within what the team has (`cash_on_hand`) or within the usual outlay for the funding path, and the top-3 bridge rows are `observed` or cited from a primary source. **Rethink** — the market case never breaks even and the team's case needs two or more `founder_guess` numbers beyond the market edge at once. **Proceed with conditions** — everything else; the conditions are the bridge's top rows written as thresholds with dates (2–4 lines, required).

## What breaks the method

- Promoting a founder's estimate to `observed` — at intake, at the gate, or in the report.
- Skipping screening because the founder "already knows the market".
- Pressing a founder to name a channel so the model can run.
- Modelling a one-off product as a subscription with high churn.
- Computing CAC as an unweighted average, or letting funnel and spend disagree.
- Calling comparable penetration a ceiling, or `far_below` a diagnosis.
- Any LTV, payback, or projection number written in prose rather than read from the script.
- Merging the founder's number and the market's into one "realistic" range — the disagreement is the finding.
- Presenting an analyst's own estimate as "the market": a derived market value carries `market_status: derived` and is shown as such.
- Citing a library entry that is `verified: false` or older than 24 months without saying so — the model flags it; the report shows the flag; `python scripts/lib_audit.py` lists them before a run.

## Author and licence

Startup Viability Check is the intellectual product of **Maxim Mikhalyov** (Vienna) — strategy and product consultant, Program Director at Moscow School of Management SKOLKOVO, startup mentor at WU VentureLAB, author of the Provify validation service; the method grows out of his practice and his EMBA research on how AI tools support early-stage founders. LinkedIn: linkedin.com/in/maximmikhalyov. Licensed under CC BY-NC 4.0 (see `LICENSE`, `NOTICE`): free for non-commercial use with attribution; commercial use — paid assessments, consulting engagements, bundling into a product or service — requires the author's written permission. Every report carries the method credit and the licence in its closing note.
