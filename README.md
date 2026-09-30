# Startup Viability Check — a Claude skill

**A first, honest financial sanity check for a startup: the founder's numbers against the market's, turned into a model, a verdict and a 90-day plan.**

Made by [Maxim Mikhalyov](https://www.linkedin.com/in/maximmikhalyov) — strategy & product consultant (Vienna), Program Director at Moscow School of Management SKOLKOVO, startup mentor at WU VentureLAB Vienna, author of the *Provify* startup-validation service and of an Executive MBA thesis on how AI tools support early-stage founders. Free to use under the MIT License; feedback and benchmark contributions are welcome.

## What it does

Give it a startup — a short description, a founder's answers, a pitch deck — and it runs the same business twice:

1. **On the founder's numbers** (price, churn, customers per month, team cost …) and
2. **on the market's numbers** for the same unit of sale — comparables' published prices, benchmark churn, funnel conversions from cited sources.

Then it shows where the two disagree, prices each disagreement (*the bridge*: "if the founder is right about churn alone, capital need falls from €88k to €51k"), shows what the outcome depends on where the founder has no number at all (*the tornado*), and writes a report a founder without a finance background can read: a verdict from four (Proceed / Proceed with conditions / Rethink / Not assessable yet), five plain sentences, monthly P&L and cash, the capital need broken down and compared with what the team has, a competitive table on the segment's defining features, the next 90 days as measurable tests, and risks with an early signal and an action.

Every number in the report is either read from the model or declared with its source; the Excel workbook reproduces the model in formulas and is recalculated with LibreOffice to prove it matches.

**Deliverables:** an interactive HTML report, a print PDF of the same content, the Excel model, and the inputs so the run can be repeated. English and Russian.

## Who it is for

Early-stage founders deciding whether to invest the next three months; mentors preparing a session; anyone who wants a quick, sourced sanity check rather than a confident score from nowhere. It is **not** investment due diligence, and the report says so on its title block.

## Install

**Claude Cowork / claude.ai:** download `startup-viability-check.skill` from the latest release and import it in *Settings → Skills*. Then ask Claude: *"Check whether this idea is viable: …"* (or in Russian: *"проверь идею …"*).

**Claude Code / any agent runtime:** clone this repository into your skills folder.

The scripts need Python 3.10+ and a few packages; two system tools add guarantees but are not required:

```bash
pip install -r requirements.txt          # openpyxl, matplotlib, weasyprint, python-docx
# optional but recommended:
#   LibreOffice (soffice)  — recalculates the Excel workbook so Python and Excel are proven equal
#   poppler (pdftotext)    — verifies the PDF page order
python scripts/check_env.py              # tells you what this machine can run and what will degrade
```

On macOS: `brew install libreoffice poppler pango` (pango is WeasyPrint's rendering library). On Debian/Ubuntu: `apt install libreoffice-calc poppler-utils libpango-1.0-0 libpangoft2-1.0-0`.

## How a run looks

1. **Screening** (one short round): who pays, for what, what they do today, what would kill the idea. Ideas without a unit of sale stop here, with a reason.
2. **Reality card** (ten minutes, no web research): the five load-bearing numbers, founder's column vs the benchmark library, run through the model.
3. **Research**: direct, indirect and displacing competitors; comparables' actual prices; benchmarks for churn, conversion and acquisition cost — with source tiers.
4. **Calibration**: one row per assumption, two columns that are never merged (the founder's number with its status, the market's with its source).
5. **Model**: `scripts/financial_model.py` — deterministic, four scenarios, bridge, tornado, capital breakdown, cash-out; `build_workbook.py` writes the Excel.
6. **Report**: `report.json` (the author's prose with placeholders into the model) → `build_report.py` → HTML / PDF, with every number verified.

`python scripts/selftest.py` runs ~800 checks including the Excel ↔ Python comparison; only `ALL PASS (python + excel)` is a release-grade result.

## Examples

`examples/` holds two complete runs — a done-for-you LinkedIn agency assessed on public data only (verdict: *not assessable yet*, with the list of what the founder must measure) and a dental-clinic SaaS with six paying customers. Each has the input, the report source, the PDF and the workbook.

## Limits (read before trusting a number)

- Team size and sales capacity are flat over the horizon: no hiring plan inside the model.
- Marketplaces are modelled one-sided (demand); supply and liquidity have to be argued in the research.
- Enterprise cash timing (annual prepayment) and hardware working capital are not modelled.
- The benchmark library is small and marked honestly: `python scripts/lib_audit.py` lists entries that are unverified or older than 24 months, and the report shows the flag next to any value that rests on one.
- Currency conversion of market values is manual (state the rate in the source).

## Contributing

Benchmark entries with a URL and a date are the most useful contribution: add a new entry to `references/benchmarks.json` following `_schema` (never overwrite an existing one) and open a pull request. Bug reports with the `input.json` that triggered them are the second most useful.

## License

MIT — see `LICENSE` and `NOTICE`. Roboto fonts under the Apache License 2.0.
