# Pass 1 — Screening

Every case starts here. The full pipeline (research → calibration → model → report) runs only when screening says the case is modelable. A polished 36-month projection for an idea with no defined buyer or no path to the first 20 paying customers is not rigour; it is false precision, and it will be read as evidence by people who did not see how thin the inputs were.

Screening is short: 20–40 minutes of the user's time, one round of questions, one page of output. It uses no web research beyond what is needed to answer the substitute filter.

## The six questions

Ask them in one batch. Record the answer, the status (`observed` / `founder_stated` / `founder_guess`; `unknown` when nothing was given), and nothing else.

1. **Who pays.** A specific role or person with a budget — not "SMEs" or "founders". If the buyer and the user differ, name both.
2. **What they do about the problem today.** The current workaround, its cost in money and hours per month, and who inside the buyer's organisation owns that cost. "Nothing" is a valid and important answer.
3. **Why the free or general-purpose alternative is not enough.** The substitute filter (below). This is the decisive question.
4. **Unit of sale.** What exactly is bought, at what price, how often: a monthly seat, a per-project fee, a percentage of a transaction, a one-time purchase. If the founder cannot say, there is no economics to model yet.
5. **Where the first 10–20 paying customers come from.** A named mechanism — a list of 15 companies the founder will call, an ad budget, a partner with an audience, an existing community. "Marketing" is not an answer. If there is no answer, record `channel: undefined` as the primary untested hypothesis. Do not press the founder to invent one.
6. **What observation would kill the idea.** One sentence — then turn it into a number the model can use. "If people stop coming back daily" becomes "D30 retention < 20 %" or "monthly churn > 25 %"; "if nobody pays" becomes "free→paid < 2 % after 60 days". The reality card and the bridge then show what that threshold does to the outcome, so a month after launch the founder looks at one metric and knows. If the founder cannot name a kill criterion, note it — it is itself a finding.

## The substitute filter (decisive)

For the buyer named in question 1, fill three lines:

| | Value | Source |
|---|---|---|
| Cost of the problem today (money + hours/month) | | |
| What the buyer gets in one hour with ChatGPT / a spreadsheet / a template / a checklist | | |
| The additional value the product delivers over that, and what the buyer pays for it | | |

The decisive question behind line 3: **what recurring work, risk, or time does the product remove beyond the one-time setup of the free alternative — and is there any signal the buyer pays for that?** A one-hour spreadsheet that then costs twenty hours a month to maintain is a different alternative from a one-hour spreadsheet that runs itself; "same thing but more convenient" can be a real business when the convenience is recurring and someone already pays for it (a tool, an assistant, a consultant).

Rule: if line 3 is empty — no recurring work removed, no risk taken over, no signal of willingness to pay — the screening verdict is **Not modelable — substitute problem**, regardless of market size or team. If line 3 names a recurring cost but no payment signal, the verdict is "Modelable with gaps" and the payment signal becomes the first experiment.

## Screening verdict

Exactly one of:

- **Modelable.** Buyer, unit of sale, and acquisition mechanism are all defined (stated or guessed, but defined); substitute filter has a concrete line 3. → Proceed to Pass 2.
- **Modelable with gaps.** One of {unit of sale, acquisition mechanism} is a guess; substitute filter passes. → Proceed to Pass 2, carry the gap as a `founder_guess` (or an `unverified` row when the market has nothing either) and put it first in "The next 90 days".
- **Not modelable — undefined unit.** No unit of sale. → Stop. Output: the three cheapest experiments that would define it (pricing interviews, pre-order page, concierge offer).
- **Not modelable — undefined channel.** No acquisition mechanism. → Stop. Output: the primary hypothesis "customers can be reached via ___" and two ways to test it in 30 days.
- **Not modelable — substitute problem.** Filter line 3 is empty. → Stop. Output: what the product would need to do that the general-purpose alternative cannot, if anything.

## Screening output (one page, in chat)

```
Screening — <startup>
Buyer:            <role> · <source tag>
Problem today:    <workaround, cost> · <source tag>
Unit of sale:     <unit, price, frequency> · <source tag>
First customers:  <mechanism> · <source tag>   (or: undefined — primary hypothesis)
Kill criterion:   <observation>

Substitute filter
  Cost today:               …
  One hour with ChatGPT/…:  …
  Additional value paid for: …   ← decisive

Verdict: <one of five>
Top unknowns (2–3): …
Cheapest tests (2–3, each with a 30-day threshold): …
```

A "Not modelable" screening is a complete, useful deliverable. It is not a failure of the process; it is the process working before the model can mislead.

---

# Pass 1b — Reality card (10 minutes, no web research)

Runs immediately after a "Modelable" or "Modelable with gaps" screening, before any research. The founder came to check numbers; this is the first place numbers appear — and it is already the shape of the final report: **the founder's case next to the market's case.**

Take the five load-bearing domains for the case's revenue unit and motion:

| Revenue unit | Five domains |
|---|---|
| subscription | pricing · cac (or monthly_budget) · monthly_churn (archetype rule!) · gross_margin · new_customers_per_month |
| project | project_value · projects_per_year · monthly_churn · cac · new_customers_per_month (+ gross_margin, required by the model) |
| transactional | gmv_per_customer_month · take_rate · monthly_churn · cac · new_customers_per_month (+ gross_margin, required by the model) |
| one_off | pricing · repeat_rate · cac · gross_margin · new_customers_per_month |

Every founder number carries a status — `observed` / `founder_stated` / `founder_guess` (a guess with no basis is `founder_guess`, not "speculative"); the model refuses a founder value without one. `fte_cost` and `funding_path` come from intake.

For each, the founder's number with its status and the library benchmark from `references/benchmarks.json` — entry id, value, tier, date, `verified` flag. Apply the library's **archetype rule** first: a product that creates a new behaviour (rather than replacing an existing habit or paid tool) takes the novelty retention entries, not the category ones. Where the library has no entry, leave `market` absent; the model runs that row on the founder's number and flags it `unverified` — do not invent a market value to complete the card.

Write the five rows straight into `assumptions{}` of a model input (`fte_cost` and the scalars from intake) and run `python scripts/financial_model.py card.json`. The markdown it prints IS the card: the comparison table, the four outcomes (founder / market / pessimistic / optimistic) and the bridge. Two lines the script adds by itself and the card must keep: **"Category estimate, not a case"** when half or more of the rows have no founder number (the card then describes the category the business is in, not the business — say so in chat), and **"Starting base: not given — the projection starts from zero"** for a live business modelled without `starting_customers` / `starting_mrr` (its capital need is then "what it costs to build this from scratch", not the company's cash position). Present it in chat with three lines under it:

```
Largest gap: <domain> — <what the bridge says it is worth in capital need / break-even>.
Capital need vs funding path: <market-case capital need> against <typical round for the stated path, library entry> — bootstrappable / pre-seed / seed / venture-scale (size only; not a statement that the round can be raised).
Kill threshold: <the founder's kill criterion as a number> → <what the model shows at that value>.
Next: full assessment (research replaces library entries with comparables and adds the evidence pack) / stop here.
```

**Gaps in the founder's favour are claims, not errors.** When a founder number beats the benchmark range by 3× or more, the card does not say "wrong" and does not assign a percentile — the library holds ranges, not distributions. It says: *outside the range this source covers; either measured — show the cohort — or the market case is the one to plan on.* Both cases stay on the card.

Entries older than 24 months or flagged `verified: false` are shown with that flag; they may anchor a card but not a report row.

## Post-revenue variant — measured numbers ARE the founder's case

If the product already has paying customers, the founder's column is filled with measured numbers (status `observed`, each with source and window: "9 % monthly churn, Stripe cohorts Jan–Jun") plus `starting_customers` / `starting_mrr`, and the market column with the category benchmarks. Any `observed` status switches the model into **measured mode**: the base becomes the business as measured, and a second bridge (`bridge_to_market`) moves one metric at a time to the category level — "what fixing churn is worth" — ranked by revenue at the last month. The report and dashboard then read "Where you stand: measured vs the category" and "What each metric is worth at the category level" instead of "If the team is right"; stories bind to `bridge_to_market_by_domain.<metric>`. A number the founder cannot show a source for is `founder_stated` and the card says so. If the founder declines to share measured numbers, run the pre-revenue card and label it "benchmarks only — founder data not provided"; do not present that as an assessment of the business.

Rules: the card never upgrades a founder number's status. A gap of 3× or more on any domain is stated in the first line. If the founder wants to stop here, the card is the deliverable; it is honest about being library-based and unresearched.
