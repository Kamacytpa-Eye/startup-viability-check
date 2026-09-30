# Intake — Case Card fields

Extract from what the user already wrote, then ask for the rest in a single batch. Group the questions so the founder can answer in one message. Skip questions already answered.

## Fields

| Field | What to capture | If missing |
|---|---|---|
| `product` | One sentence: what it is, what it does | ask |
| `customer` | Who buys — role, company size or consumer segment, region | ask |
| `problem` | The pain being solved and how it's solved today | ask |
| `business_model` | Archetype: B2B SaaS seat-based / B2B SaaS flat / B2C subscription / marketplace / transactional / services / hardware | infer, confirm |
| `pricing` | Price point and unit (per seat, per month, per transaction, one-off) | ask — required for the model |
| `revenue_unit` | subscription / project / transactional / one_off — what exactly is bought and how often | infer, confirm; if undefined → screening stops |
| `unit_of_sale` | What exactly is sold, in one line — format, scope, buyer ("two-hour online AI workshop for an agency team") | ask; the market column must price this and nothing else |
| `motion` | Primary go-to-market motion from Axis 1 in `growth.md` (paid / organic / viral / PLG / founder-led / inside sales / enterprise / partner / developer) | infer from what's said, confirm. If nothing → record as undefined hypothesis (see below) |
| `driver` | The one number that caps that motion: ad budget, organic traffic, reps, founder hours, partner reach… (the "driver question" column in `growth.md`) | ask; if unknown, benchmark for a solo early-stage team and mark it `founder_guess` (with no market data the row is `unverified`). **Paid motion: budget is mandatory** — CAC is derived from it |
| `channels` | Optional finer channel math: `audience_size`, `ctr_pct`, `conversion_pct` per channel | ask only if founder has it |
| `stage` | Idea / prototype / first users / paying customers | ask |
| `funding_path` | bootstrap / pre-seed / seed / series A — how the founder intends to fund the next 18 months | ask; the report reads the market-case capital need against the typical round for this path (`typical_round` entries) |
| `traction` | Any real numbers: users, revenue, retention, waitlist | ask |
| `team` | Headcount, FTE cost region | ask — drives capital need |
| `runway` | Cash available (→ `cash_on_hand` in the model input, gives the cash-out month) or months of runway | ask |
| `sales_share_of_payroll` | Share of the team's time / payroll that sells (founder hours on calls, SDRs) — 0–1 | ask; needed for a meaningful LTV/CAC in any sales-led motion |
| `upfront_investment` | What must be built or bought before the first dollar: inventory, content library, hardware tooling, licences, certification | ask — media, hardware, marketplace-with-subsidies and regulated products live or die here |
| `fixed_costs_monthly` | What keeps being paid every month regardless of customer count, beyond the team: content, data licences, infra floor, rent | ask |
| `free_months` | Length of a free trial or free period a new customer gets before paying | ask if a trial exists; a 90-day trial delays revenue by a quarter and loses part of the cohort before it pays |
| `starting_customers`, `starting_mrr` | Post-revenue only: paying customers and monthly revenue right now, with source and window (Stripe export, invoices) | ask when there is any revenue; both together, status `observed` only with the export, else `founder_stated`. The model starts from this base instead of zero |
| `months` | Projection horizon, integer 12–120 (default 36) | ask only if the founder plans on a different horizon; every output labels its last month |
| `founder_numbers` | Every number the founder has for the model's domains (`calibration.md`): price, margin, churn or repeat rate, expansion, CAC or ad budget, new customers per month, cost per FTE | record each as a POINT with its status tag; these become the `founder` column of the Assumptions Pack |
| `website` | URL if exists — read it for context | optional |

## Source tags on every number

- `observed` — measured and shown (export, cohort table, invoices)
- `founder_stated` — founder asserts it as fact ("our churn is 4%")
- `founder_guess` — founder frames it as an estimate ("probably around $200"); a number with no basis at all is still `founder_guess`
- `unknown` — not provided → the row runs on the market value (`filled_from_market`), or, with no market value either, screening stops

These are the only statuses the model accepts for a founder number. Nothing becomes `observed` at intake unless the measurement is shown.

## No motion named

If the founder cannot say where the first 10–20 paying customers will come from, do not push for an answer — a channel invented under questioning is worse than none. Record `channel: undefined` as the primary untested hypothesis. Screening (`screening.md`) returns "Not modelable — undefined channel" with two 30-day tests; the full model is not built.

## Points stay points

Founders give points ("€59", "3 % churn", "CAC around €150"). Keep them as points — they are the founder's column of the Assumptions Pack and the founder case of the model. Do not ask the founder for a range and do not build one around their number: the range belongs to the market side (benchmark low/high), where it describes the uncertainty of the benchmark, not of the founder. If the founder's point lies far outside the market range, nothing is stretched; the gap is the finding, and the bridge shows what it is worth.

## Channel math

For each channel:

```
customers_per_month = audience_size × (ctr_pct / 100) × (conversion_pct / 100)
```

Example: LinkedIn outreach, 50,000 reachable × 2% CTR × 10% conversion = 100 customers/month.

If the founder can't estimate a channel, offer typical ranges for the archetype and mark the result `founder_guess`. Sum across channels for `total_customers_per_month`.

## Batch question template

> Before I research this, I need a few things you haven't mentioned:
>
> **Money:** What will you charge, and per what (seat / month / transaction)? Any idea of gross margin?
> **Growth:** Where will the first 100 customers come from — ads, content/SEO, your own outreach, a sales team, partners or a marketplace? And the one number behind it: monthly ad budget / current traffic / meetings you can book per week / number of reps / partner audience size.
> **Where you are:** Idea, prototype, or real users? Any numbers — signups, revenue, retention?
> **Team & cash:** How many people, where are they based, how much runway? What has to be built or bought before the first sale, and what will you keep paying monthly whether or not customers show up (content, licences, infrastructure)? Is there a free trial, and how long?
>
> Guesses are fine — I'll mark them as guesses.
