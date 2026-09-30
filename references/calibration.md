# Calibration — the Assumptions Pack (founder side, market side)

The model runs the business twice: on the founder's numbers and on the market's. Calibration is where those two columns are filled, domain by domain, and never merged. The output is `assumptions{}` in the model input plus the Assumptions Pack table the founder confirms at gate 3.

## One row per domain, two columns

| Column | What it holds | Where it comes from |
|---|---|---|
| `founder` | One number — the founder's own figure | Intake. Points, not ranges: the founder says "€59", "3 %", "around €150". Status tags it (below). Absent → the row runs on the market value and is flagged `filled_from_market`; the report says so, and in the workbook the founder cell is a formula over the market range, so the link survives edits. |
| `market` | One number or `[low, high]` — what benchmarks or comparables say | Research + `references/benchmarks.json`. The model uses the midpoint as the market case and the edges as the pessimistic / optimistic cases. Absent → the row runs on the founder's number, flagged `unverified`; the report says so and lists it under "what you still need to prove"; in the workbook the market cells are formulas over the founder cell. |
| `status` | Provenance of the FOUNDER number: `observed` / `founder_stated` / `founder_guess` | Intake tags survive unchanged. `observed` only with a measurement the founder can show (Stripe export, cohort table, ad-platform report). |
| `source` | Provenance of the MARKET number: library entry id + tier, or "Competitor A pricing page (primary)" | Required whenever `market` is given — the model refuses a market value without a source. |

**Where the market number comes from — say it.** Every market value carries `market_status`: `cited` (a named comparable or primary figure), `library` (a `benchmarks.json` entry — the id in `source`), or `derived` (the analyst's own calculation or rule of thumb: a funnel scaled to the team, a capacity estimate). When the field is absent the model infers it from the source text and the report shows the inferred status; write it explicitly. A `derived` value is not market evidence and the report labels it "analyst's estimate" in the comparison; when it sits at the top of the tornado it becomes the first measurement to ask for. Library entries that are `verified: false` or dated more than 24 months ago are flagged on the row and in `warnings`; they may anchor a reality card but should be replaced by research before the report.

**Same product on both sides.** The market value must describe the same unit of sale the founder sells — same format, same scope, same buyer. A published price for a full-day corporate workshop is not the market price of the founder's two-hour online session; a churn figure for annual contracts is not the market churn of a monthly plan. When the only evidence is for a different format, leave `market` absent (the row runs on the founder's number, flagged `unverified`) and put the other format's numbers into a repricing experiment in "the next 90 days". Write the line's `unit_of_sale` in the model input so the pack states what is being priced.

**Show the derivation.** A market value is either a library entry's value used as is (cite the id; the model checks it exists) or a stated calculation from cited figures ("30–50 %/yr client churn → 1−(1−a)^(1/12) = 2.9–5.6 %/mo"). A range the author cannot derive from something cited is not a market value.

**Never merge.** Do not widen the founder's number into a range to swallow the market value, and do not move the market value toward the founder's. The gap between the two columns is the finding; the bridge prices it.

**Never upgrade status.** When the founder confirms or edits the pack at gate 3, the edited number stays `founder_stated`; agreement with a hypothesis is not evidence for it. Say this in one line when presenting the gate.

## Domains (exactly the model's)

| Domain | Unit | Applies to | Typical market sources |
|---|---|---|---|
| `pricing` | currency per customer-month (subscription) or per purchase (one_off) | subscription, one_off | comparables' pricing pages (primary); `price.*` entries |
| `project_value` | currency per project (revenue to the company) | project | comparables' rate cards; evidence pack |
| `projects_per_year` | projects per client per year | project | `churn.agency.project.*`, staffing repeat data |
| `gmv_per_customer_month` | currency | transactional | comparables' disclosed GMV per account |
| `take_rate` | % | transactional | platform fee pages (primary) |
| `gross_margin` | % | all | archetype table in `growth.md` Axis 2; `margin.*` |
| `monthly_churn` | % per month | subscription, project, transactional | `churn.*` — apply the archetype rule (new-behaviour products use the novelty entries) |
| `expansion` | % per month (optional, default 0) | retention units | `expansion.*`; NRR annual → monthly: `((NRR/100)^(1/12) − 1) × 100` |
| `repeat_rate` | % of buyers who buy again per cycle | one_off | `repeat.*` |
| `cac` | currency per new customer, CASH only, ≥ 0 | all motions except paid | `cac.*`. Money actually spent per new customer: tools, ads, events, travel, partner fees. Founder hours are never cash: salaried founders sit in `fte × fte_cost` / `shared_fixed_monthly`; unsalaried founders' hours go into the scalar `founder_time_cost_per_customer` (hours × opportunity cost / 160), which produces `ltv_cac_incl_time` and `payback_incl_time` next to the cash ratios but never touches the cash flow or the capital need. A purely organic channel may have cash CAC 0 — the cash LTV/CAC is then reported as "∞ (no cash cost to acquire)". With a channel table the founder's CAC IS the volume-weighted table (a separate founder number that disagrees is refused) |
| `monthly_budget` | currency per month | paid motion only (CAC = budget ÷ new customers) | founder's budget vs what comparables spend |
| `new_customers_per_month` | new customers per month at full ramp | all | the funnel (`growth.md` Axis 1): driver × benchmark conversions; `capacity.*` |
| `fte_cost` | currency per FTE per month | all | `fte.cost.*` by region |

**Team cost across lines.** A team that serves several revenue lines goes into `shared_fixed_monthly` at the top level, not into one line's `fte`; otherwise that line carries the whole burn and the other line's unit economics and bridge look free. Per-line `fte` is for staff dedicated to that line only.

`sales_share_of_payroll` (0–1, top level or per line): the share of payroll that sells — founder hours on sales, SDRs, AEs. With it the model reports a **loaded CAC** (cash CAC + selling payroll per new customer at full ramp), and the headline LTV/CAC, payback and the signal table use the loaded ratio; without it a sales-led business shows a cash-only ratio in the hundreds, which is not information. `cash_on_hand`: the money the team actually has — gives a cash-out month and the comparison the verdict uses first (before the funding-path outlay).

Scalars that are the same in every case (not compared): `growth{motion, ramp_mid_month, ramp_k, sales_cycle_months, funnel[]}`, `fte`, `fixed_costs_monthly`, `upfront_investment`, `free_months`, `starting_customers` / `starting_mrr`, `repeat_interval_months`, `comparable_benchmark{segment_size, comparable_penetration_pct}`. Each still needs a source line in the pack.

`funding_path` (top level, required: bootstrap / pre_seed / seed / series_a) and `currency` (top level, required: EUR / USD / GBP …) are what the market-case capital need is read against: a VERIFIED typical-round entry in the library (`bootstrap.capital`, `round.pre_seed.us.2025` — Carta; the EU entries are unverified and are not used). If the entry is in another currency, give `fx_rates` (`{"USD_per_EUR": 1.08}`) or the comparison is reported as `unavailable` with the reason; the report says so instead of a position.

Domains that inform the pack but are not model inputs — `sales_cycle` (→ `growth.sales_cycle_months`), `conversion_range` (→ inside the funnel that produces `new_customers_per_month`), `trust_friction` (→ conversion and cycle choices) — are documented in the funnel table, not as assumption rows.

## Market value: precedence and confidence

1. Actual figures of 2–3 direct comparables (primary tier) — the market range is their spread; name them in `source`.
2. A survey-tier benchmark for the archetype (n stated).
3. A secondary-tier benchmark or practitioner roundup.
4. Nothing — leave `market` absent; the row is `unverified` and becomes the first experiment.

Confidence follows the tier of the source actually used (`benchmarks.json` `_schema.confidence_from_tier`: primary → medium, survey → medium, secondary → low). `high` is reserved for `observed` numbers of this business. Entries flagged `verified: false` in the library may anchor a reality card but must be replaced by research before they carry a report row. Convert every market figure to the case currency at a stated rate and record the rate in `source`; the only automatic conversion today is the typical-round comparison via `fx_rates` (planned: a `currency` field per market value with automatic conversion at a recorded rate).

Defaults (CAC 10–1000, margin 20–90, churn 0.5–30) do not exist in this method: a domain with no founder number and no market evidence is a screening failure, not a wide range.

## Assumptions Pack format (gate 3)

```
| Domain | Founder (status) | Market (source · tier) | Gap | Note |
|---|---|---|---|---|
| pricing | €59 (founder_stated) | €40–80, mid €60 (price.validation_tools.2026 · primary) | 1.0× | inside the comparables' band |
| monthly_churn | 3 % (founder_guess) | 5–8 % (churn.saas.smb.2026 · secondary) | 2.2× | founder more optimistic than the category |
| cac | — (filled from market) | €150–300 (cac.microsaas.paid.2025 · secondary) | — | no founder number; ask for the channel plan |
| new_customers_per_month | 20 (founder_stated) | 8–15 (funnel: 500 signups × 4–15 % trial→paid, ChartMogul 2026) | 1.7× | above the funnel's benchmark conversion |
```

Below the table: the scalars with their sources, and `fragility_flags` (1–4 items) — where a small move in one number flips the outcome, each with Likelihood and Reversibility. The pack maps 1:1 onto the model input's `assumptions{}`; there is no translation step in which a number can change.
