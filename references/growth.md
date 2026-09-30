# Growth model — two axes

A case is classified on two independent axes. Axis 1 decides **how new customers arrive** (the funnel and what caps it). Axis 2 decides **what a customer is worth** (margin, churn, expansion, capital). Keep them separate: a SaaS can be sold by any motion; a paid-ads funnel can sell anything.

Benchmarks below are starting values with typical sources. Step 1 research refines them for the specific segment. They fill the MARKET column of the Assumptions Pack; the founder's own driver number and conversions fill the founder column — the two are never merged (`calibration.md`). Every funnel step in the report says where its number came from.

---

## Axis 1 — Go-to-market motion (the growth driver)

Pick one primary motion, optionally one secondary. Ask the founder the **driver question** for that motion; it is the one input the model cannot do without.

| # | Motion | What caps growth | Driver question to the founder | Funnel (monthly) | Starting benchmarks | Ramp to full capacity |
|---|---|---|---|---|---|---|
| 1 | **Paid acquisition** (search, social, display) | Budget | Monthly ad budget? | `budget / CPC × landing CR × trial→paid` | CPC $0.5–3 B2C, $3–15 B2B SMB (WordStream); landing CR 2–5 %; trial→paid 4–15 % no-card, 25–60 % card (ChartMogul Conversion Report 2026, n=200) | 2–3 months (learning phase) |
| 2 | **Organic / content / SEO** | Time + reach | Current monthly organic visits? Content cadence? | `visits × signup CR × trial→paid` | Signup CR 1–3 %; SEO compounds 6–12 months (Indie Hackers 2025); content CAC $20–40 | 9–12 months |
| 3 | **Viral / referral** | k-factor + cycle | Any existing users? Invite mechanism? | `active users × invites × accept rate` → k | k 0.2–0.5 typical, >1 rare and short-lived; cycle 7–30 days | Compounds; only drives growth when k ≥ ~0.5 on top of another motion |
| 4 | **PLG / self-serve** | Traffic × activation | Monthly signups (or traffic)? | `signups × activation × free→paid` | Activation 20–40 %; free→paid 2–5 % freemium, 8–15 % trial (OpenView PLG benchmarks) | 3–6 months |
| 5 | **Founder-led sales** | Founder hours | Hours/week on sales? Meetings booked/week? | `meetings/month × demo→close`, lag = sales cycle | 8–15 meetings/week max for one founder; demo→close 15–30 % SMB, 10–20 % mid-market; cycle 14–60 days SMB | Immediate, but hard cap ~10–20 deals/month; degrades when product work resumes |
| 6 | **Inside sales** (SDR/AE) | Headcount | Number of SDRs/AEs (now, planned)? | `reps × meetings/rep/month × demo→close`, lag = cycle | 15–30 meetings/SDR/month; demo→close 15–25 %; cycle 30–90 days; rep ramp 3 months | Per rep: 3 months to 100 % |
| 7 | **Enterprise / field sales** | AE capacity × cycle | AEs? Average contract value? | `AEs × deals/AE/year`, lag = cycle | 4–8 deals/AE/year; cycle 120–270 days; win rate 20–30 % of qualified; tenders add 3–6 months | Per AE: 6–9 months to first close |
| 8 | **Partner / channel / marketplace listing** | Partner reach × listing CR | Which partners/marketplaces? Their audience size? | `partner reach × listing CTR × install→paid` or `resellers × deals/reseller` | App-store/marketplace CTR 0.5–2 %; install→paid 3–8 %; reseller ramp 6 months; partner takes 15–30 % | 6–9 months to meaningful volume |
| 9 | **Community / developer-led** | Adoption + docs | GitHub stars / community size? Free tier usage? | `signups × activation × usage→paid` | Free→paid 1–3 %; usage-based expansion 2–5 %/month; 12+ months to monetize | 12–18 months |

If the founder names no motion at all, stop at gate 0: "Where will the first 100 customers come from — ads, content, your own outreach, a sales team, partners?" A business without an answer has nothing to model.

If the founder names a motion but has no driver number (budget / reps / traffic), the founder column is empty and the row runs on the benchmark starting point for a solo early-stage team of that motion (`filled_from_market`); it goes first in "The next 90 days".

---

## Axis 2 — Business type (the unit economics)

| Type | Revenue unit | Gross margin | Monthly churn | Expansion / month | Capital note |
|---|---|---|---|---|---|
| **SaaS — seat-based** | per seat/month | 70–90 % | 1–3 % mid-market, 3–7 % SMB | 1.5–3 % (seat growth) | Team cost only |
| **SaaS — flat / usage** | per account or per unit | 70–90 % (usage: 50–75 % if infra-heavy) | 2–8 % | usage 2–5 %, flat 0.5–1.5 % | Infra scales with usage |
| **Consumer subscription / app** | per user/month | 60–85 % (store fees 15–30 %) | 5–15 %; single-purpose products 30–90 % | 0.5–1.5 % | Store ranking drives organic |
| **Marketplace** | take rate × GMV | 40–70 % of take | supply-side 3–8 %, demand 5–15 % | 0.5–2 % (volume) | Needs liquidity before revenue; supply acquisition is a second funnel |
| **D2C / e-commerce / hardware** | per order | 20–50 % after COGS, shipping, returns | repeat rate 20–40 % (not churn) | reorder cadence | Inventory = capital; returns 5–25 % |
| **Services / agency** | per project or retainer | 40–65 % | 5–10 % retainers; projects one-off | upsell 2–4 % | Capacity = billable hours; growth = hiring |
| **Transactional / fintech** | volume × take rate | 30–70 % | 3–10 % | 1–3 % | Compliance cost, float |

`capital_intensity` (cost per FTE per month) is set by region, not type: US/W-Europe 6–12k; E-Europe/LatAm 2–5k; S/SE Asia 1.5–4k; unknown 3–8k.

---

## Comparable benchmark (a reference, not a ceiling)

Independent of the funnel, compute what comparable companies achieved:

```
segment_size           = number of target customers in the addressable segment (bottom-up count, not a $ TAM)
comparable_penetration = share of segment reached by 2–3 comparable products after ~3 years (from research; if none found, use 1–3 % and say so in the source)
reference_customers_3y = segment_size × comparable_penetration
```

Compare the bottom-up customer count at month 36 with the reference (the reference is a three-year figure, so the comparison is always at month 36; a horizon under 36 months skips it with a note). The script reports the ratio and a position: `above_comparables` (ratio > 1), `within_range`, `far_below_comparables` (ratio < 0.1).

What the position means — and does not mean:

- `above_comparables`: the funnel assumptions outrun what named comparables achieved. This is a prompt to re-examine the funnel, not proof it is wrong; a better channel or a smaller, better-defined segment can legitimately beat comparables. Say which.
- `far_below_comparables`: the funnel delivers a fraction of what comparables reached. Possible causes include weak distribution, a segment defined too broadly, or comparables that are not actually comparable. Name the most likely cause and the observation that would confirm it; do not write "distribution gap" as a diagnosis.
- Never call the reference a "ceiling" or "market limit". Other companies' penetration is evidence about the market, not a bound on this company.

## Blended CAC and the budget check

- With per-channel volumes and CACs: **volume-weighted** average, `Σ(customers_i × cac_i) / Σ customers_i`. Never a simple average of channel CACs, and never averaged with a calibrated figure — an unweighted mean lets one expensive low-volume channel dominate.
- **Paid motion:** CAC is derived, `monthly_budget / new_customers_per_month`. The funnel table produces the customer count; the budget is the founder's driver number. If a separately calibrated CAC disagrees by more than 30 %, the script refuses to run — one of the two is wrong and the report must not paper over it.
- Acquisition spend in the projection is always `new customers × blended CAC`, so cash flow and funnel cannot drift apart.

---

## Ramp (S-curve)

Growth capacity ramps, customers follow. The script applies a logistic ramp to the driver:

```
capacity(m) = full_capacity / (1 + exp(-k × (m − m_mid)))
```

`m_mid` = month at which 50 % of capacity is reached; `k` sets steepness. Defaults by motion (from the "Ramp" column): paid m_mid=2, organic m_mid=8, PLG m_mid=4, founder-led m_mid=1, inside sales m_mid=3 per rep, enterprise m_mid=7, partner m_mid=6, developer-led m_mid=10. Founder-stated ramp overrides.

---

## Funnel table in the report

Always show the funnel as a table with a source column, e.g. for paid:

| Step | Value | Source |
|---|---|---|
| Monthly budget | $3 000 | founder stated |
| CPC | $1.80 | benchmark — WordStream 2025, B2C fitness |
| Clicks | 1 667 | computed |
| Landing → trial | 3 % | benchmark — Unbounce 2025 |
| Trial → paid | 8 % | benchmark — Userpilot 2026, no-card |
| **New customers / month at full capacity** | **4** | computed |

This table is what turns "where did the number come from" into a one-glance answer.
