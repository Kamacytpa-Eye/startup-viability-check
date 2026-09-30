# Evidence Pack — DentiQueue (Step 1) · Verification (Step 2) · Assumptions Pack (Step 3)

## Evidence

| # | Claim | Value | Source | Tier / quality | Date |
|---|---|---|---|---|---|
| 1 | Niedergelassene Zahnärzt:innen Wien | 954 (angestellt 326; gesamt 1 740) | https://www.zahnaerztekammer.at/fileadmin/content/oezak/daten_und_zahlen/2026/standesm_september.pdf | primary (ÖZÄK Standesmeldung) | 2026-09 |
| 2 | Niedergelassene Zahnärzt:innen Österreich | 3 768 (gesamt 5 625) | same | primary | 2026-09 |
| 3 | Dr. Flex (DE) price, per practice, incl. digitale Nachrückerliste + reminders | Flat €99 (1 calendar) / €139 (2) / €169 (3); Starter €39 + €3.99 per booking; monthly cancellable | https://dr-flex.de/aerzte/preis · https://dr-flex.de/produkt/digitale-warteliste | primary (published prices) | 2026 |
| 4 | Doctolib (DE/AT) price, per Behandler:in | Light/Pro €139; Aufbau ~€229; All-in-One to €499; AT ~€130–200; long minimum terms | https://adfera.de/ratgeber/doctolib-kosten/ (partner page; secondary for prices) · https://info.doctolib.de/preis/ | secondary | 2026-08 |
| 5 | US dental comms suites (Weave, RevenueWell, Adit, Yapi) price | $200–500 / location / month; waitlist fill included | https://expertity.com/toolpick/best-dental-patient-communication-software.html | secondary | 2026 |
| 6 | Dr. Flex scale | 14 100+ practitioners, founded 2014, bootstrapped (no external funding) | https://dr-flex.de/ressourcen/blog/10-jahre-drflex | primary (company statement) | 2025 |
| 7 | Doctolib scale | 500 000+ health professionals in Europe, 120 000 in DE | https://info.doctolib.de/ | primary (company statement) | 2026 |
| 8 | Dental no-show rate | 7.4 % (Helsinki public, n=2.5 M appointments); ~15 % average, up to 30 % (vendor roundups) | https://pmc.ncbi.nlm.nih.gov/articles/PMC12535098/ · https://clerri.com/blog/dental-patient-no-show-statistics | primary (study) / secondary | 2025 / 2026 |
| 9 | Value of an empty dental chair-hour | $475–800 per dentist hour (US) | https://scottleune.com/blog/dental-practice-no-shows-cost-revenue-drain/ | secondary | 2025 |
| 10 | SMB SaaS monthly churn | 3–7 %; <$300k ARR median 6.5 % (ChartMogul, 2 500+ cos) | library churn.saas.smb.2026 · https://saasflywheel.io/blog/saas-churn-rate-benchmarks-2026 | secondary | 2026-01 |
| 11 | SaaS gross margin | 70–90 % | library margin.saas (KeyBanc/OpenView) — STALE (2024), no fresher primary found in this run | survey | 2024 |
| 12 | Pre-seed founder salary | ~$50k/yr US pre-seed (≈ €3 800/mo at 1.10); DACH founders paid above UK (Creandum) | https://kruzeconsulting.com/... · https://foundercomp.creandum.com/ | secondary | 2025 |
| 13 | Demo→close SMB, founder-led | 15–30 % | library conv.demo.close.smb | secondary | 2025 |
| 14 | Founder-led capacity | 8–15 meetings/week for one founder full-time on sales | library capacity.founder_led — UNVERIFIED | secondary | 2025 |
| 15 | Typical pre-seed round | $250k–1M (Carta, n=50 316, US) — EU entry round.pre_seed.eu unverified | library round.pre_seed.us.2025 | survey | 2026-02 |

## Competitors

### Direct (same problem, same approach)
| Name | Price | Target | Published figures | Notes |
|---|---|---|---|---|
| Dr. Flex (Berlin) | €99–169 flat / practice / month, or €39 + €3.99 per booking; monthly cancellable | Arzt- und Zahnarztpraxen DE (AT presence not confirmed) | 14 100+ practitioners; bootstrapped since 2014 | Digitale Nachrückerliste + automated reminders = DentiQueue's core feature set, plus online booking and AI phone |
| Doctolib (AT via Doctory) | ~€130–200 / Behandler / month in AT; long contracts | all outpatient practices | 500k+ professionals in Europe | Waitlist (earlier-slot) + SMS/e-mail reminders built in; per-practitioner billing makes multi-dentist clinics expensive |
| Weave / RevenueWell / Adit (US) | $200–500 / location | US dental | fill rates 60–70 % vs 20 % manual (vendor claim) | Not in AT; price anchor for the category |

### Indirect (same problem, different approach)
| Alternative | Cost to buyer | Why chosen |
|---|---|---|
| Reception phones the waitlist by hand | assistant time (~€25/h); 20 % fill rate per vendor claim | zero setup, no new tool, already staffed |
| Practice-management software (PVS) reminder module (CGM, Dampsoft, Zahnarztsoftware AT) | included in PVS licence, often SMS billed per message | already installed; one vendor |
| "Do nothing" / overbooking | lost chair-hours; patient friction | small clinics with full books do not feel the pain |

### Displacers
| Displacer | Risk | Defence |
|---|---|---|
| Doctolib ships automatic slot-refill in Austria to its whole base | high — feature already exists as "Warteliste" | none identified beyond price (flat per clinic vs per Behandler) and monthly cancellability |
| PVS vendors add waitlist automation natively | medium — reminders already native; refill is a small step | integration depth / speed; no data moat named |
| General-purpose AI (ChatGPT + calendar) | low — needs real-time calendar integration and SMS; a clinic will not build it | workflow, not knowledge |
| Behaviour shift (online self-booking reduces no-shows) | medium over 5 years | none — the need shrinks as booking platforms spread |

## Risks outside the model
- GDPR / health data (patient names, phone numbers, appointment types): processor agreements with every clinic; SMS provider outside EU is a compliance issue.
- Integration dependency on PVS calendars (write access to the schedule) — the API terms of 3–4 Austrian PVS vendors decide reach.
- Channel concentration: all 6 clinics from the founders' own Vienna network and one association.

## Verification (Step 2) — Case Card vs evidence
| Founder number | Verdict | Note |
|---|---|---|
| Price €149/clinic/month | confirmed (in band) | Dr. Flex flat €99–169 per practice for the same feature set; Doctolib €139 per practitioner |
| 0 % churn over 5 months | unverified | 6 clinics, 5 months — too small a base; category 3–7 %/month |
| Gross margin 91.9 % | confirmed (upper edge) | SaaS 70–90 %; SMS costs scale with usage — hosting+SMS €12/clinic is founder_stated |
| 8 demos/month, 25 % close | unverified / plausible | close rate inside the 15–30 % band; 8 demos/month is far below the 8–15/week capacity benchmark (unverified entry) |
| CAC €100 cash | unverified | no library entry for founder-led cash CAC; the number is €200 tools+events ÷ 2 signups |
| 6 clinics / €894 MRR | unverified | no export shown; 6 × €149 = €894 is arithmetically consistent |
| Kill criterion >3/20 in 3 months | — | = 5.3 %/month, inside the category band: the founder's kill line is the market's normal |
| Goal 60 clinics at M12 | contradicted by own funnel | 6 + 12 × 2 = 30 at the founder's own 2/month; 60 needs ~4.5/month |

## Assumptions Pack (Step 3)
| Domain | Founder (status) | Market (source · tier · market_status) | Gap | Note |
|---|---|---|---|---|
| pricing | €149 (founder_stated) | €99–169, mid €134 (Dr. Flex Booking-Flat, published prices · primary · cited) | 1.1× | inside band; Dr. Flex bundles online booking too |
| gross_margin | 91.9 % (founder_stated) | 70–90 % (margin.saas · survey · library — STALE 2024) | 1.15× | SMS volume per clinic is the risk to margin |
| monthly_churn | 0 % (founder_stated) | 3–7 % (churn.saas.smb.2026 · secondary · library) | ∞ | 6 clinics × 5 months cannot show churn; first thing to prove |
| expansion | 0 (default) | 0 | — | single flat price; no upsell modelled |
| cac | €100 (founder_stated) | — (no applicable entry; unverified) | — | €200/month tools+events ÷ 2 signups; log it per signed clinic |
| new_customers_per_month | 2 (founder_stated) | 1.2–2.4 (8 demos/month × conv.demo.close.smb 15–30 % · derived) | 1.1× | the driver (8 demos) is the founder's; only the close rate is benchmarked |
| fte_cost | €3 000 (founder_stated) | €3 788–8 182 (low: Kruze US pre-seed founder salary $50k/yr ÷ 12 ÷ 1.10; high: fte.cost.region mid $9 000 ÷ 1.10 · derived) | 2.0× | the founders' wish, not a wage; drives capital need, not the business |

Scalars: fte 2 (founder_stated) · fixed_costs_monthly 0 (tools/events sit in CAC) · upfront 0 (product live) · free_months 1 (GUESS — trial length not given) · starting 6 clinics / €894 MRR (founder_stated) · sales_share_of_payroll 0.5 (GUESS) · founder_time_cost_per_customer €281 (15 h × €3 000/160 — library method entry cac.founder_led.timecost, GUESS) · comparable_benchmark: segment 3 768 niedergelassene Zahnärzt:innen Österreich (ÖZÄK 2026-09, primary), penetration 1–3 % (no 3-year comparable found — flagged speculative) · funding_path pre_seed · cash_on_hand €40 000 · months 36 · fx 1.10 USD/EUR (recorded, approximate).

fragility_flags:
1. monthly_churn 0 → 5 %: LTV drops from the 60-month cap to ~€2 400; likelihood high (base of 6 too small), reversibility — irreversible once clinics leave.
2. fte_cost €3 000 → €8 000: capital need ×3; likelihood medium (only if they hire); reversible.
3. new_customers 2 → 1.2: break-even leaves the horizon; likelihood medium (network exhausts); reversible with a second channel.
4. free_months 1 → 3 (Doctolib-style discount period): delays revenue a quarter; low; reversible.
