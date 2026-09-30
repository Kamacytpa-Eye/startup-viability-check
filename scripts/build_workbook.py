#!/usr/bin/env python3
"""
Build the financial model workbook (.xlsx) and chart images (.png).

Usage:
    python build_workbook.py input.json out_dir [--name "Startup"] [--lang ru|en] [--currency €]

Single line → <name>_financial_model.xlsx (Dashboard, Growth, Inputs, Founder, Market, Pessimistic, Optimistic) + chart PNGs
Inputs sheet: one row per assumption with four blue cells — Founder · Market low · Market high (Market = average of the
two) — so the founder can edit either side and watch both cases move. Four case sheets share one formula structure.
Multi-line  → ONE workbook: a formula-driven "Combined" dashboard (shared overhead is a blue input there) followed by
              a block of sheets per line ("<Line> Inputs", "<Line> Founder/Market/Pessimistic/Optimistic", "<Line> Summary", "<Line> Growth"),
              plus combined charts (revenue, cash, units summed over lines). Changing a blue cell on any line's
              Inputs sheet updates that line's sheets AND the Combined dashboard.

Every number in the workbook is a formula off the Inputs sheet(s) (blue cells), including the
comparable-benchmark block. Same math as financial_model.py; recalc.py must be run after build.
Print layout: every sheet is set to landscape, fit-to-width, so the workbook exports to PDF page by page.
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from financial_model import run_all, run_line, validate, simulate, case_values, LTV_HORIZON, CASES, DOMAINS  # noqa: E402

CASE_TITLE = {"founder": "Founder", "market": "Market", "pessimistic": "Pessimistic", "optimistic": "Optimistic"}
CASE_SHEETS = [CASE_TITLE[c] for c in CASES]

BLUE = Font(name="Arial", color="0000FF"); BLACK = Font(name="Arial"); GREEN = Font(name="Arial", color="008000")
BOLD = Font(name="Arial", bold=True); HDR = Font(name="Arial", bold=True, color="FFFFFF")
HDR_FILL = PatternFill("solid", fgColor="1F3864"); KEY_FILL = PatternFill("solid", fgColor="FFFF00")
MONEY = '#,##0;(#,##0);-'; PCT = '0.0%'; MULT = '0.0x'


def sheet_name(prefix, base):
    """Excel sheet names: ≤ 31 chars, no []:*?/\ ."""
    n = f"{prefix}{base}" if prefix else base
    for ch in '[]:*?/\\': n = n.replace(ch, "-")
    return n[:31]


def q(name):
    """Quote a sheet name for use in a formula."""
    return "'" + name.replace("'", "''") + "'"


def print_setup(ws, landscape=True):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5)
    ws.print_options.horizontalCentered = True


def hdr(ws, row, labels):
    for c, h in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=c, value=h); cell.font = HDR; cell.fill = HDR_FILL


def build_inputs(ws, p):
    """Inputs sheet. Columns: A label · B Founder (blue) · C Market (=AVERAGE(D,E)) · D Market low (blue) · E Market high (blue) · F status · G source."""
    unit = p["unit"]
    ws["A1"] = "Assumptions — founder vs market"; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    ws["A2"] = f"Revenue unit: {unit}. Blue cells are inputs. Founder = the founder's number; Market = midpoint of the benchmark range (low/high feed the pessimistic and optimistic cases)."
    ws["A2"].font = Font(name="Arial", italic=True)
    hdr(ws, 4, ["Assumption", "Founder", "Market (mid)", "Market low", "Market high", "Founder status", "Market source"])
    rm = {}; r = 5
    fmt_for = {"money": MONEY, "pct": PCT, "count": "0.00"}

    def dom_row(key, label, s):
        nonlocal r
        kind = s["kind"]; scale = 0.01 if kind == "pct" else 1
        ws.cell(row=r, column=1, value=label).font = BLACK
        for col, val in ((2, s["founder"]), (4, s["market_low"]), (5, s["market_high"])):
            c = ws.cell(row=r, column=col, value=val * scale); c.font = BLUE; c.fill = KEY_FILL; c.number_format = fmt_for[kind]
        c = ws.cell(row=r, column=3, value=f"=AVERAGE(D{r},E{r})"); c.number_format = fmt_for[kind]
        # fills stay LINKED: a founder value taken from the market follows the market range; a market value taken from the founder follows the founder cell
        if s["fill"] == "filled_from_market":
            c = ws.cell(row=r, column=2, value=f"=AVERAGE(D{r},E{r})"); c.font = GREEN; c.fill = PatternFill(fill_type=None); c.number_format = fmt_for[kind]
        elif s["fill"] in ("unverified", "derived_from_channels"):   # market = founder: keep the link
            for col in "DE":
                c = ws[f"{col}{r}"]; c.value = f"=B{r}"; c.font = GREEN; c.fill = PatternFill(fill_type=None); c.number_format = fmt_for[kind]
        if key == "cac" and p["channels"]:
            rm["_cac_row"] = r   # founder CAC becomes a formula over the channel table once that table exists (below)
        ws.cell(row=r, column=6, value=s["status"] + (f" · {s['fill']}" if s["fill"] else ""))
        ws.cell(row=r, column=7, value=s["source"])
        rm[key] = r; r += 1

    for key, s in p["dom"].items():
        dom_row(key, s["label"].capitalize(), s)
    if unit == "project":
        ws.cell(row=r, column=1, value="Revenue per client-month (derived)").font = BLACK
        for col in "BCDE":
            ws[f"{col}{r}"] = f"={col}{rm['project_value']}*{col}{rm['projects_per_year']}/12"; ws[f"{col}{r}"].number_format = MONEY
        rm["arpu0"] = r; r += 1
    elif unit == "transactional":
        ws.cell(row=r, column=1, value="Revenue per customer-month (derived)").font = BLACK
        for col in "BCDE":
            ws[f"{col}{r}"] = f"={col}{rm['gmv_per_customer_month']}*{col}{rm['take_rate']}"; ws[f"{col}{r}"].number_format = MONEY
        rm["arpu0"] = r; r += 1
    elif unit == "subscription":
        rm["arpu0"] = rm["pricing"]

    r += 1
    ws.cell(row=r, column=1, value="Scalars (same in every case)").font = BOLD; r += 1
    g = p["growth"]
    scalars = [("Team size (FTE)", "fte", p["fte"], "0"), ("Fixed monthly overhead (content, licences, infra floor)", "fixed", p["fixed"], MONEY),
               ("Upfront investment before first revenue", "upfront", p["upfront"], MONEY),
               ("Free months per new customer (long trial)", "free", p.get("free_months", 0), "0"),
               ("Founder time per new customer, value of unpaid hours (not cash; ratios only)", "time_cost", p.get("time_cost", 0), MONEY),
               ("Starting paying customers (post-revenue only, measured)", "start_c", p.get("start_customers", 0), "#,##0"),
               ("Starting monthly revenue (post-revenue only, measured)", "start_mrr", p.get("start_mrr", 0), MONEY),
               ("Ramp: month at 50% capacity", "ramp_mid", g["ramp_mid"], "0.0"), ("Ramp: steepness k (0 = no ramp)", "ramp_k", g["ramp_k"], "0.00"),
               ("Sales-cycle lag (months)", "lag", g["lag"], "0")]
    if unit == "one_off":
        scalars.append(("Repeat interval (months)", "interval", p["interval"], "0"))
    if p["comparable"]:
        scalars.append(("Comparable benchmark: segment size (customers)", "segment", p["comparable"]["segment"], "#,##0"))
    for label, key, val, fmt in scalars:
        ws.cell(row=r, column=1, value=label).font = BLACK
        c = ws.cell(row=r, column=2, value=val); c.font = BLUE; c.number_format = fmt; c.fill = KEY_FILL
        rm[key] = r; r += 1
    if p["comparable"]:
        ws.cell(row=r, column=1, value="Comparable penetration after ~3 years (founder/market = mid; low/high edges)").font = BLACK
        lo, hi = p["comparable"]["pen"][0] / 100, p["comparable"]["pen"][1] / 100
        for col, val in (("D", lo), ("E", hi)):
            c = ws[f"{col}{r}"]; c.value = val; c.font = BLUE; c.fill = KEY_FILL; c.number_format = PCT
        for col in "BC":
            ws[f"{col}{r}"] = f"=AVERAGE(D{r},E{r})"; ws[f"{col}{r}"].number_format = PCT
        rm["pen"] = r; r += 1

    r += 1
    ws.cell(row=r, column=1, value="Acquisition channels — the founder's CAC is the volume-weighted average of this table").font = BOLD; r += 1
    hdr(ws, r, ["Channel", "Customers / month", "Channel CAC", "Effective CAC"]); r += 1
    rm["ch_start"] = r
    for ch in p["channels"] or [{"name": "(none — CAC from the assumption row)", "customers_per_month": None, "cac": None}]:
        ws.cell(row=r, column=1, value=ch.get("name"))
        ws.cell(row=r, column=2, value=ch.get("customers_per_month")).font = BLUE
        c = ws.cell(row=r, column=3, value=ch.get("cac")); c.font = BLUE; c.number_format = MONEY
        ws.cell(row=r, column=4, value=f"=C{r}").number_format = MONEY
        r += 1
    rm["ch_end"] = r - 1
    if "_cac_row" in rm:
        cr_ = rm["_cac_row"]; cs, ce = rm["ch_start"], rm["ch_end"]
        c = ws[f"B{cr_}"]; c.value = f"=SUMPRODUCT(B{cs}:B{ce},D{cs}:D{ce})/SUM(B{cs}:B{ce})"; c.font = GREEN; c.fill = PatternFill(fill_type=None); c.number_format = MONEY
    ws.column_dimensions["A"].width = 52
    for col in "BCDE": ws.column_dimensions[col].width = 14
    ws.column_dimensions["F"].width = 22; ws.column_dimensions["G"].width = 60
    print_setup(ws, landscape=True)
    return rm


def case_col(p, key, case):
    """Inputs column holding this domain's value for a case: B founder · C market mid · D/E edges by direction."""
    if case == "founder": return "B"
    if case == "market": return "C"
    better = p["dom"][key]["better_high"] if key in p["dom"] else True
    if key == "arpu0" and p["unit"] in ("project", "transactional"): better = True
    return ("D" if better else "E") if case == "pessimistic" else ("E" if better else "D")


def build_scenario(ws, case, rm, p, inputs_sheet="Inputs"):
    I = q(inputs_sheet) + "!"; unit = p["unit"]; months = p["months"]; name = CASE_TITLE[case]
    R = lambda key: f"{I}{case_col(p, key, case)}{rm[key]}"
    ws["A1"] = f"{name} case"; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    cs, ce = rm["ch_start"], rm["ch_end"]
    weighted = f"SUMPRODUCT({I}B{cs}:B{ce},{I}D{cs}:D{ce})/SUM({I}B{cs}:B{ce})"
    cac_f = f"={R('monthly_budget')}/B9" if "monthly_budget" in rm else f"={R('cac')}"   # one source: the Inputs row (channel-weighted there when a channel table exists)
    pen_col = {"founder": "B", "market": "C", "pessimistic": "D", "optimistic": "E"}[case]
    # B3.. header block
    rows = [
        ("Revenue per customer-month (ARPU₀)" if unit != "one_off" else "Price per purchase",
         (f"={R('arpu0')}" if unit in ("subscription",) else f"={I}{case_col(p, 'arpu0', case)}{rm['arpu0']}") if unit != "one_off" else f"={R('pricing')}", MONEY),  # B3
        ("Gross margin", f"={R('gross_margin')}", PCT),                                                # B4
        ("Monthly churn" if unit != "one_off" else "Repeat rate", f"={R('monthly_churn') if unit != 'one_off' else R('repeat_rate')}", PCT),  # B5
        ("Monthly expansion" if unit != "one_off" else "Repeat interval (months)",
         f"={R('expansion')}" if unit != "one_off" else f"={I}B{rm['interval']}", PCT if unit != "one_off" else "0"),  # B6
        ("Blended CAC", cac_f, MONEY),                                                                 # B7
        ("Fixed burn / month", f"={I}B{rm['fte']}*{R('fte_cost')}+{I}B{rm['fixed']}", MONEY),          # B8
        ("New customers / month at full capacity", f"={R('new_customers_per_month')}", "0.0"),         # B9
        ("LTV (lifetime contribution, 60-mo cap)",
         (f"=B3*B4*(1-B5)^{I}B{rm['free']}*IF(ABS(1-(1-B5)*(1+B6))<0.000001,MAX(0,{LTV_HORIZON}-{I}B{rm['free']}),(1-((1-B5)*(1+B6))^MAX(0,{LTV_HORIZON}-{I}B{rm['free']}))/(1-(1-B5)*(1+B6)))"
          if unit != "one_off" else f"=B3*B4*IF(B5<=0,1,(1-B5^ROUNDUP({LTV_HORIZON}/B6,0))/(1-B5))"), MONEY),   # B10  one-off: purchases at 0, iv, 2iv … while k·iv < 60
        ("LTV / CAC (cash)", '=IF(B7>0,B10/B7,"n/a")', MULT),                                            # B11
        ("Payback (months, cumulative; \"none\" = not within 60)",
         # retention: smallest T with contrib·(1−q^T)/(1−q) ≥ CAC  →  T = ln(1 − CAC(1−q)/contrib)/ln(q); q=1 → CAC/contrib
         (f'=IF(B3*B4<=0,"none",IF(B7<=0,1+{I}B{rm["free"]},IF((1-B5)*(1+B6)<=0,IF(B7<=B3*B4*(1-B5)^{I}B{rm["free"]},1+{I}B{rm["free"]},"none"),IF(ABS(1-(1-B5)*(1+B6))<0.000001,IF(B7/(B3*B4*(1-B5)^{I}B{rm["free"]})<={LTV_HORIZON}-{I}B{rm["free"]},ROUNDUP(B7/(B3*B4*(1-B5)^{I}B{rm["free"]}),0)+{I}B{rm["free"]},"none"),'
          f'IF(1-B7*(1-(1-B5)*(1+B6))/(B3*B4*(1-B5)^{I}B{rm["free"]})<=0,"none",IF(ROUNDUP(LN(1-B7*(1-(1-B5)*(1+B6))/(B3*B4*(1-B5)^{I}B{rm["free"]}))/LN((1-B5)*(1+B6)),0)<={LTV_HORIZON}-{I}B{rm["free"]},'
          f'ROUNDUP(LN(1-B7*(1-(1-B5)*(1+B6))/(B3*B4*(1-B5)^{I}B{rm["free"]}))/LN((1-B5)*(1+B6)),0)+{I}B{rm["free"]},"none"))))))'
          if unit != "one_off" else
          # one-off: K purchases needed: contrib·(1−r^K)/(1−r) ≥ CAC → K = ceil(ln(1 − CAC(1−r)/contrib)/ln r); months = (K−1)·interval + 1
          f'=IF(B3*B4<=0,"none",IF(B7<=B3*B4,1,IF(B5<=0,"none",IF(1-B7*(1-B5)/(B3*B4)<=0,"none",'
          f'IF((ROUNDUP(LN(1-B7*(1-B5)/(B3*B4))/LN(B5),0)-1)*B6+1<={LTV_HORIZON},(ROUNDUP(LN(1-B7*(1-B5)/(B3*B4))/LN(B5),0)-1)*B6+1,"none")))))'),
         "0"),                                                                                          # B12
    ]
    for i, (label, f, fmt) in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=label).font = BLACK
        c = ws.cell(row=i, column=2, value=f); c.font = GREEN if f.startswith("=" + q(inputs_sheet)) else BLACK; c.number_format = fmt
    hr = 15
    heads = ["Month", "Ramp", "New customers (arrivals)", "Paying customers" if unit != "one_off" else "Purchases (units)", "ARPU (derived)", "Revenue",
             "Gross profit", "Acquisition spend", "Fixed burn", "Net cash flow", "Cumulative cash", "Lowest net from here on"]
    hdr(ws, hr, heads)
    mid, k, lag = f"{I}B{rm['ramp_mid']}", f"{I}B{rm['ramp_k']}", f"{I}B{rm['lag']}"
    for m in range(1, months + 1):
        r = hr + m; prev = r - 1
        ws.cell(row=r, column=1, value=m)
        ws.cell(row=r, column=2, value=f"=IF({k}=0,1,1/(1+EXP(-{k}*(A{r}-{mid}))))").number_format = "0.00"
        ws.cell(row=r, column=3, value=f"=IF(A{r}-{lag}<1,0,$B$9*IF({k}=0,1,1/(1+EXP(-{k}*(A{r}-{lag}-{mid})))))").number_format = "#,##0.0"
        if unit == "one_off":
            iv = f"{I}B{rm['interval']}"
            ws.cell(row=r, column=4, value=f"=C{r}+IF(A{r}>{iv},$B$5*OFFSET(D{r},-{iv},0),0)").number_format = "#,##0.0"
            ws.cell(row=r, column=5, value="=$B$3").number_format = MONEY
        else:
            Fc = f"{I}B{rm['free']}"
            pnew = f"IF(A{r}-{Fc}<1,0,OFFSET(C{r},-{Fc},0)*(1-$B$5)^{Fc})"   # arrivals F months ago that survived the free period
            ws.cell(row=r, column=4, value=(f"={I}B{rm['start_c']}*(1-$B$5)+{pnew}" if m == 1 else f"=D{prev}*(1-$B$5)+{pnew}")).number_format = "#,##0.0"
            ws.cell(row=r, column=5, value=f"=IF(D{r}>0,F{r}/D{r},0)").number_format = MONEY
        if unit == "one_off":
            ws.cell(row=r, column=6, value=f"=D{r}*E{r}").number_format = MONEY
        else:
            # cohort-consistent revenue: last month's revenue decays by churn and grows by expansion; newly-paying cohort adds ARPU₀
            ws.cell(row=r, column=6, value=(f"={I}B{rm['start_mrr']}*(1-$B$5)*(1+$B$6)+{pnew}*$B$3" if m == 1 else f"=F{prev}*(1-$B$5)*(1+$B$6)+{pnew}*$B$3")).number_format = MONEY
        ws.cell(row=r, column=7, value=f"=F{r}*$B$4").number_format = MONEY
        ws.cell(row=r, column=8, value=f"=$B$9*B{r}*$B$7").number_format = MONEY
        ws.cell(row=r, column=9, value="=$B$8").number_format = MONEY
        ws.cell(row=r, column=10, value=f"=G{r}-H{r}-I{r}").number_format = MONEY
        ws.cell(row=r, column=11, value=(f"=J{r}-{I}B{rm['upfront']}" if m == 1 else f"=K{prev}+J{r}")).number_format = MONEY
        ws.cell(row=r, column=12, value=f"=MIN(J{r}:J{hr + months})").number_format = MONEY   # break-even needs net ≥ 0 from this month to the end
    last = hr + months; sr = last + 2
    ws.cell(row=sr, column=1, value="Break-even month (net ≥ 0 from then on)").font = BOLD
    ws.cell(row=sr, column=2, value=f'=IFERROR(INDEX(A{hr+1}:A{last},MATCH(TRUE,INDEX(L{hr+1}:L{last}>=0,0),0)),"none")')
    ws.cell(row=sr + 1, column=1, value="Peak capital need").font = BOLD
    ws.cell(row=sr + 1, column=2, value=f"=MAX(0,{I}B{rm['upfront']},-MIN(K{hr+1}:K{last}))").number_format = MONEY   # cash before month 1 is −upfront
    if p["comparable"] and unit != "one_off" and months >= 36:
        ws.cell(row=sr + 2, column=1, value="Reference customers, 3y (segment × comparable penetration)").font = BOLD
        ws.cell(row=sr + 2, column=2, value=f"={I}B{rm['segment']}*{I}{pen_col}{rm['pen']}").number_format = "#,##0"
        ws.cell(row=sr + 3, column=1, value="Bottom-up customers, month 36 (same 3-year window as the reference)").font = BOLD
        ws.cell(row=sr + 3, column=2, value=f"=D{hr+36}").number_format = "#,##0"
        ws.cell(row=sr + 4, column=1, value="Ratio to reference").font = BOLD
        ws.cell(row=sr + 4, column=2, value=f"=IF(B{sr+2}>0,B{sr+3}/B{sr+2},0)").number_format = "0.00"
        ws.cell(row=sr + 5, column=1, value="Position").font = BOLD
        ws.cell(row=sr + 5, column=2, value=f'=IF(B{sr+4}>1,"above_comparables",IF(B{sr+4}<0.1,"far_below_comparables","within_range"))')
    ws.column_dimensions["A"].width = 44
    for i in range(2, 12):
        ws.column_dimensions[get_column_letter(i)].width = 15
    ws.freeze_panes = f"A{hr+1}"
    print_setup(ws)
    return hr, last, sr


def kpi_tiles(ws, tiles, row=4):
    """Six formula tiles across columns A..L (two columns each), value on `row`, label below. Fits one landscape page."""
    for i, (lab, f, fmt) in enumerate(tiles):
        col = 1 + i * 2
        c = ws.cell(row=row, column=col, value=f); c.font = Font(name="Arial", bold=True, size=15, color="1F3864"); c.number_format = fmt
        c.fill = PatternFill("solid", fgColor="F2F4F8"); c.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row, column=col + 1).fill = PatternFill("solid", fgColor="F2F4F8")
        ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + 1)
        l = ws.cell(row=row + 1, column=col, value=lab); l.font = Font(name="Arial", size=8, color="59595B"); l.fill = PatternFill("solid", fgColor="F2F4F8")
        l.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        ws.cell(row=row + 1, column=col + 1).fill = PatternFill("solid", fgColor="F2F4F8")
        ws.merge_cells(start_row=row + 1, start_column=col, end_row=row + 1, end_column=col + 1)
    ws.row_dimensions[row].height = 30; ws.row_dimensions[row + 1].height = 34
    for i in range(1, 13):
        ws.column_dimensions[get_column_letter(i)].width = 14
    ws.column_dimensions["A"].width = 44


def build_summary(ws, refs, p, titles, title="Dashboard"):
    hr, last, sr = refs; months = p["months"]
    S = {sc: q(titles[sc]) for sc in CASE_SHEETS}; F, M = S["Founder"], S["Market"]
    ws["A1"] = title; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    ws["A2"] = "Founder case vs market case — every tile is a formula; change the blue cells on Inputs and this page updates."; ws["A2"].font = Font(name="Arial", italic=True)
    tiles = [("LTV / CAC (cash) — founder | market", f'=IF(ISNUMBER({F}!B11),TEXT({F}!B11,"0.0")&"×","n/a")&" | "&IF(ISNUMBER({M}!B11),TEXT({M}!B11,"0.0")&"×","n/a")', "@"),
             ("Payback, months — founder | market", f'={F}!B12&" | "&{M}!B12', "@"),
             ("Break-even month — founder | market", f'={F}!B{sr}&" | "&{M}!B{sr}', "@"),
             ("Peak capital need — founder | market", f'=TEXT({F}!B{sr+1},"#,##0")&" | "&TEXT({M}!B{sr+1},"#,##0")', "@"),
             (f"Revenue month {months} — founder | market", f'=TEXT({F}!F{hr+months},"#,##0")&" | "&TEXT({M}!F{hr+months},"#,##0")', "@"),
             ("Revenue per customer needed for LTV/CAC = 3 (market)", f"=IF({M}!B4*{M}!B10>0,3*{M}!B7/({M}!B10/{M}!B3),0)", MONEY)]
    kpi_tiles(ws, tiles)
    hdr(ws, 7, ["Metric"] + CASE_SHEETS)
    items = [("Blended CAC", "B7", MONEY), ("LTV (lifetime gross-margin contribution, 60-mo cap)", "B10", MONEY), ("LTV / CAC (cash)", "B11", MULT), ("Payback (months, cumulative)", "B12", "0"),
             ("Gross margin", "B4", PCT), ("Break-even month", f"B{sr}", "0"), ("Peak capital need", f"B{sr+1}", MONEY)]
    items += [(f"Revenue month {k}", f"F{hr+k}", MONEY) for k in (12, 24, 36) if k < months]
    items += [(f"Revenue month {months}", f"F{hr+months}", MONEY),
              ((f"Purchases month {months} (units)" if p["unit"] == "one_off" else f"Customers month {months}"), f"D{hr+months}", "#,##0")]
    if p["comparable"] and p["unit"] != "one_off" and months >= 36:
        items += [("Reference customers (3y)", f"B{sr+2}", "#,##0"), ("Ratio to reference", f"B{sr+4}", "0.00"), ("Position vs comparables", f"B{sr+5}", "@")]
    r = 8
    for label, cell, fmt in items:
        ws.cell(row=r, column=1, value=label)
        for c, sc in enumerate(CASE_SHEETS, start=2):
            x = ws.cell(row=r, column=c, value=f"={S[sc]}!{cell}"); x.font = GREEN; x.number_format = fmt
        r += 1
    cr = r + 2
    ws.cell(row=cr, column=1, value="Month").font = BOLD
    heads = [f"{k} {sc}" for k in ("Rev", "Cash", "Units") for sc in CASE_SHEETS]
    for c, h in enumerate(heads, start=2):
        ws.cell(row=cr, column=c, value=h).font = BOLD
    for m in range(1, months + 1):
        rr = cr + m; ws.cell(row=rr, column=1, value=m)
        for i, sc in enumerate(CASE_SHEETS):
            ws.cell(row=rr, column=2 + i, value=f"={S[sc]}!F{hr+m}").number_format = MONEY
            ws.cell(row=rr, column=6 + i, value=f"={S[sc]}!K{hr+m}").number_format = MONEY
            ws.cell(row=rr, column=10 + i, value=f"={S[sc]}!D{hr+m}").number_format = "#,##0"
    add_charts(ws, cr, months, "Purchases per month (units)" if p["unit"] == "one_off" else "Customers")
    ws.print_area = [f"A1:M{cr + months}", "O1:X52"]   # page 1: tiles + tables; page 2: the three charts at readable size
    print_setup(ws)


def add_charts(ws, cr, months, units_title, ncase=4):
    cats = Reference(ws, min_col=1, min_row=cr + 1, max_row=cr + months)
    for title, c0, anchor in [("Revenue by case", 2, "O4"), ("Cumulative cash", 2 + ncase, "O20"), (units_title, 2 + 2 * ncase, "O36")]:
        ch = LineChart(); ch.title = title; ch.height = 7.5; ch.width = 15
        ch.add_data(Reference(ws, min_col=c0, max_col=c0 + ncase - 1, min_row=cr, max_row=cr + months), titles_from_data=True); ch.set_categories(cats)
        ws.add_chart(ch, anchor)


def build_combined(ws, line_refs, months, shared):
    """Formula-driven combined dashboard for multi-line workbooks, one column block per case.
    line_refs: {line_name: (titles, (hr, last, sr), p)} where titles maps sheet base names to the ACTUAL sheet titles."""
    ws["A1"] = "Combined — all revenue lines, founder vs market"; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    ws["A2"] = "Every cell is a formula over the line sheets. Change a blue cell on any '<Line> Inputs' sheet and this page updates."; ws["A2"].font = Font(name="Arial", italic=True)
    ws["A3"] = "Shared monthly overhead (not attributable to one line)"; c = ws["B3"]; c.value = shared; c.font = BLUE; c.number_format = MONEY; c.fill = KEY_FILL
    ws["A7"] = "Upfront investment, all lines"; ws["A7"].font = BOLD
    ws["B7"] = "=" + "+".join(f"{q(t['Inputs'])}!B{p_['_rm']['upfront']}" for t, _, p_ in line_refs.values()); ws["B7"].number_format = MONEY
    n = len(CASE_SHEETS); cr = 14
    ws.cell(row=cr, column=1, value="Month").font = BOLD
    heads = [f"{k} {sc}" for k in ("Rev", "Cash", "Units", "Net", "MinNet→") for sc in CASE_SHEETS]
    for c_, h_ in enumerate(heads, start=2):
        ws.cell(row=cr, column=c_, value=h_).font = BOLD
    for m in range(1, months + 1):
        rr = cr + m; ws.cell(row=rr, column=1, value=m)
        for i, sc in enumerate(CASE_SHEETS):
            rev = "+".join(f"{q(t[sc])}!F{refs[0]+m}" for t, refs, _ in line_refs.values())
            cash = "+".join(f"{q(t[sc])}!K{refs[0]+m}" for t, refs, _ in line_refs.values())
            units = "+".join(f"{q(t[sc])}!D{refs[0]+m}" for t, refs, _ in line_refs.values())
            ws.cell(row=rr, column=2 + i, value=f"={rev}").number_format = MONEY
            ws.cell(row=rr, column=2 + n + i, value=f"={cash}-$B$3*A{rr}").number_format = MONEY
            ws.cell(row=rr, column=2 + 2 * n + i, value=f"={units}").number_format = "#,##0"
            cash_col = get_column_letter(2 + n + i); net_col_ = get_column_letter(2 + 3 * n + i)
            ws.cell(row=rr, column=2 + 3 * n + i, value=(f"={cash_col}{rr}+$B$7" if m == 1 else f"={cash_col}{rr}-{cash_col}{rr-1}")).number_format = MONEY
            ws.cell(row=rr, column=2 + 4 * n + i, value=f"=MIN({net_col_}{rr}:{net_col_}{cr + months})").number_format = MONEY
    first, lastr = cr + 1, cr + months
    hdr(ws, 8, ["Case", "Break-even month", "Peak capital need", f"Revenue month {months}", f"Cumulative cash month {months}"])
    for i, sc in enumerate(CASE_SHEETS):
        cash_col = get_column_letter(2 + n + i); net_col = get_column_letter(2 + 4 * n + i)   # "lowest net from here on" column
        ws.cell(row=9 + i, column=1, value=sc)
        ws.cell(row=9 + i, column=2, value=f'=IFERROR(INDEX(A{first}:A{lastr},MATCH(TRUE,INDEX({net_col}{first}:{net_col}{lastr}>=0,0),0)),"none")')
        ws.cell(row=9 + i, column=3, value=f"=MAX(0,$B$7,-MIN({cash_col}{first}:{cash_col}{lastr}))").number_format = MONEY
        ws.cell(row=9 + i, column=4, value=f"={get_column_letter(2 + i)}{lastr}").number_format = MONEY
        ws.cell(row=9 + i, column=5, value=f"={cash_col}{lastr}").number_format = MONEY
    tiles = [("Break-even — founder | market", '=B9&" | "&B10', "@"), ("Peak capital need — founder | market", '=TEXT(C9,"#,##0")&" | "&TEXT(C10,"#,##0")', "@"),
             (f"Revenue month {months} — founder | market", '=TEXT(D9,"#,##0")&" | "&TEXT(D10,"#,##0")', "@"),
             (f"Cumulative cash month {months} — founder | market", '=TEXT(E9,"#,##0")&" | "&TEXT(E10,"#,##0")', "@"),
             ("Upfront, all lines", "=B7", MONEY), ("Revenue lines", str(len(line_refs)), "0")]
    kpi_tiles(ws, tiles, row=4)
    ws.column_dimensions["A"].width = 30
    add_charts(ws, cr, months, "Units (summed over lines, not deduplicated)")
    ws.print_area = [f"A1:Q{lastr}", "O1:X52"]
    print_setup(ws)


def build_growth(ws, p):
    print_setup(ws, landscape=False)
    ws["A1"] = "Growth funnel (documentation of where the capacity number came from)"; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    g = p["growth"]; r = 3
    ws.cell(row=r, column=1, value=f"Motion: {g['motion']}  ·  ramp 50% at month {g['ramp_mid']:.0f}  ·  lag {g['lag']} mo").font = BOLD; r += 2
    hdr(ws, r, ["Funnel step", "Value", "Source"]); r += 1
    for f in g["funnel"]:
        ws.cell(row=r, column=1, value=f.get("step")); ws.cell(row=r, column=2, value=str(f.get("value"))); ws.cell(row=r, column=3, value=f.get("source")); r += 1
    ws.cell(row=r + 1, column=1, value="The resulting capacity is the blue 'New customers per month at full capacity' input. Edit it there.").font = Font(name="Arial", italic=True)
    ws.column_dimensions["A"].width = 52; ws.column_dimensions["B"].width = 18; ws.column_dimensions["C"].width = 50


CHART_L = {
    "en": {"mrr": "Monthly revenue", "cash": "Cumulative cash", "customers": "Active customers", "purchases": "Purchases per month (units)", "mixed": "Units (not deduplicated across lines)",
           "month": "Month", "all": " — all lines", "founder": "Founder", "market": "Market", "pessimistic": "Pessimistic", "optimistic": "Optimistic"},
    "ru": {"mrr": "Выручка в месяц", "cash": "Накопленный денежный поток", "customers": "Активные клиенты", "purchases": "Покупок в месяц (единиц)", "mixed": "Единицы (сумма по линиям, без дедупликации)",
           "month": "Месяц", "all": " — все линии", "founder": "Команда", "market": "Рынок", "pessimistic": "Пессимистичный", "optimistic": "Оптимистичный"},
}


def money_fmt(cur):
    from chart_style import fmt_money
    return lambda x, _: fmt_money(x, cur)


def make_pngs(scen: dict, out_dir: str, suffix: str = "", lang: str = "en", cur: str = "$"):
    from chart_style import COL as colors, apply as _apply_style
    _apply_style(plt)
    styles = {"founder": "-", "market": "-", "pessimistic": "--", "optimistic": "--"}
    L = CHART_L.get(lang, CHART_L["en"])
    ul = scen["market"]["projection"][0].get("units_label", "customers")
    units_title = L.get(ul, L["mixed"])
    if suffix == " — all lines": suffix = L["all"]
    for key, title, fname in [("mrr", L["mrr"], "chart_mrr.png"), ("cumulative", L["cash"], "chart_cash.png"), ("customers", units_title, "chart_customers.png")]:
        fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
        for sc in CASES:
            rows = scen[sc]["projection"]
            ax.plot([x["month"] for x in rows], [x[key] for x in rows], label=L[sc], color=colors[sc], linewidth=2.2 if sc in ("founder", "market") else 1.3, linestyle=styles[sc])
        ax.set_title(title + suffix, fontsize=12, loc="left"); ax.set_xlabel(L["month"]); ax.axhline(0, color="#999", linewidth=.8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(money_fmt(cur) if key != "customers" else (lambda x, _: f"{x:,.0f}"))); ax.grid(alpha=.3); ax.legend(frameon=False)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        fig.tight_layout(); fig.savefig(os.path.join(out_dir, fname)); plt.close(fig)


def _new_sheet(wb, wanted):
    """Create a sheet with exactly the wanted title; fail loudly instead of letting openpyxl silently append '1'."""
    if wanted.lower() in {n.lower() for n in wb.sheetnames}:   # Excel sheet names are case-insensitive
        raise ValueError(f"sheet title collision: {wanted!r} already exists (case-insensitively)")
    return wb.create_sheet(wanted)


def build_line(wb, cfg, prefix=""):
    """Add one revenue line's sheet block to wb. Returns (titles, refs, p); titles holds the actual sheet titles."""
    p = validate(cfg)
    titles = {b: sheet_name(prefix, b) for b in ["Summary", "Growth", "Inputs"] + CASE_SHEETS}
    ws_sum = _new_sheet(wb, titles["Summary"]); ws_gr = _new_sheet(wb, titles["Growth"]); ws_in = _new_sheet(wb, titles["Inputs"])
    rm = build_inputs(ws_in, p); p["_rm"] = rm
    refs = None
    for case in CASES:
        refs = build_scenario(_new_sheet(wb, titles[CASE_TITLE[case]]), case, rm, p, inputs_sheet=ws_in.title)
    build_summary(ws_sum, refs, p, titles, title=("Dashboard" if not prefix else f"Dashboard — {prefix.strip(' —')}"))
    build_growth(ws_gr, p)
    return titles, refs, p


def unique_prefixes(names):
    """Sheet-name prefixes that stay unique after truncation: 'Subscription basic' / 'Subscription pro' → 'Subscripti#1 — ' / 'Subscripti#2 — '."""
    base = [n[:12].strip() for n in names]
    lower = [b.lower() for b in base]          # Excel sheet names are case-insensitive: 'Basic' and 'basic' collide
    out = []
    for i, b in enumerate(base):
        if lower.count(lower[i]) > 1:
            b = f"{names[i][:10].strip()}#{i+1}"
        out.append(b + " — ")
    if len({o.lower() for o in out}) != len(out):
        raise ValueError(f"cannot derive unique sheet prefixes from line names {names}")
    return out


def build_one(cfg, out_dir, name):
    res = run_line(cfg)            # validate and simulate first: a refused config must not leave a workbook behind
    wb = Workbook(); wb.remove(wb.active)
    build_line(wb, cfg)
    path = os.path.join(out_dir, f"{name}_financial_model.xlsx"); wb.save(path)
    return path, res["cases"]


def build_multi(cfg, out_dir, name):
    wb = Workbook(); wb.remove(wb.active)
    ws_c = wb.create_sheet("Combined")
    line_refs = {}
    names = [ln.get("name", f"line{i+1}") for i, ln in enumerate(cfg["lines"])]
    for ln, lname, prefix in zip(cfg["lines"], names, unique_prefixes(names)):
        line_refs[lname] = build_line(wb, ln, prefix)
    run_all(cfg)   # validate everything (incl. horizons, duplicate names) before writing
    months = next(iter(line_refs.values()))[2]["months"]
    build_combined(ws_c, line_refs, months, float(cfg.get("shared_fixed_monthly", 0)))
    path = os.path.join(out_dir, f"{name}_financial_model.xlsx"); wb.save(path)
    return path


def model_hash(model: dict) -> str:
    """Fingerprint of a model output; build_report checks the chart PNGs were made from the same model.json it verifies against."""
    import hashlib
    return hashlib.sha256(json.dumps(model, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def file_hash(path: str) -> str:
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def write_manifest(out_dir: str, name: str, model: dict, files: list, context: dict | None = None) -> None:
    """Written AFTER the images exist; carries the model fingerprint, a hash of every PNG and the rendering context
    (line, lang, currency), so build_report can tell 'charts from another model', 'images replaced' and 'dashboard of another line'."""
    import hashlib
    st = {"model_hash": model_hash(model), "files": files, "png_hash": {f: file_hash(os.path.join(out_dir, f)) for f in files}, "context": context or {}}
    st["sig"] = hashlib.sha256(json.dumps(st, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]   # binds context + hashes; a hand edit invalidates it
    json.dump(st, open(os.path.join(out_dir, name), "w"))


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cfg = json.load(open(sys.argv[1])); out_dir = sys.argv[2]; os.makedirs(out_dir, exist_ok=True)
    for stale in ("charts.json",):   # an interrupted build must not leave a fresh manifest next to old images
        try: os.remove(os.path.join(out_dir, stale))
        except FileNotFoundError: pass
    name = sys.argv[sys.argv.index("--name") + 1].strip().replace(" ", "_") if "--name" in sys.argv else "startup"
    lang = (sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "en").lower()
    cur = sys.argv[sys.argv.index("--currency") + 1] if "--currency" in sys.argv else "$"
    ctx = {"line": None, "lang": lang, "currency": cur}
    if "lines" not in cfg:
        path, scen = build_one(cfg, out_dir, name); make_pngs(scen, out_dir, lang=lang, cur=cur)
        write_manifest(out_dir, "charts.json", run_all(cfg), ["chart_mrr.png", "chart_cash.png", "chart_customers.png"], ctx)
        print(json.dumps({"xlsx": [path], "charts": ["chart_mrr.png", "chart_cash.png", "chart_customers.png"]})); return
    paths = [build_multi(cfg, out_dir, name)]
    allres = run_all(cfg)
    comb = {sc: {"projection": [dict(r, units_label="mixed") for r in allres["combined"][sc]["projection"]]} for sc in CASES}
    make_pngs(comb, out_dir, " — all lines", lang=lang, cur=cur)
    write_manifest(out_dir, "charts.json", allres, ["chart_mrr.png", "chart_cash.png", "chart_customers.png"], ctx)
    print(json.dumps({"xlsx": paths, "charts": ["chart_mrr.png", "chart_cash.png", "chart_customers.png"],
                      "combined": {sc: {k: v for k, v in allres["combined"][sc].items() if k != "projection"} for sc in CASES}}, indent=1))


if __name__ == "__main__":
    main()
