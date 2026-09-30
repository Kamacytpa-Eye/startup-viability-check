"""PDF renderer for the viability report — HTML + CSS rendered with WeasyPrint.

Called by build_report.build() when the output path ends in .pdf, AFTER every check has passed
(schema, placeholders, number verification, requirements, register lint); the content it receives
is the same rendered report the .docx renderer gets. Page order is the same and is verified on
the produced PDF (comparison on page 1, dashboard on page 2).

Design — friendly information style, infographic first:
  • Roboto (bundled in assets/fonts, Cyrillic + €), ink text on white, generous spacing, rounded cards.
  • Two colours carry the whole comparison: TEAM orange (#F28C28) and MARKET indigo (#3B4CCA) —
    the same pair as the dashboard PNG — plus a verdict colour, green/red for good/bad, soft greys.
  • Page 1: verdict hero, the story as a numbered timeline, KPI tiles with two coloured values,
    and the comparison as RANGE BARS — a market band with the team's number as a dot on it.
  • Assumption stories as cards with icons (believes / evidence / stakes / test); the market and
    team cases open with three big numbers; competitors in a table with layer pills and the
    startup's row highlighted; 90-day items as step cards; risks as cards with severity pills.
  • Every number still comes from the verified report content — this file only lays it out.
"""
import base64
import html
import os

from build_report import (fmt_mult, mlabel, PAGE1_ROWS, COST_DOMAINS, page1_rows, VERDICT_COLORS, _bridge_rows, _dv, default_kpis, fmt_value, gen_bridge, gen_comparable,
                          gen_comparison, gen_growth, gen_outcomes, gen_unit_economics, get_ref, lead, money, required_charts,
                          top_bridge_domains)

E = html.escape
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
TEAM, MARKET, INK, MUTED, LINE, SOFT, SOFT2 = "#F28C28", "#3B4CCA", "#1B1F3B", "#6B7280", "#E5E7EB", "#F5F6FA", "#EEF0FF"
GOOD, BAD, WARN = "#16A34A", "#DC2626", "#D97706"
PESS_C, OPT_C = "#DC2626", "#16A34A"

ICON = {
    "bulb": '<svg viewBox="0 0 24 24"><path d="M9 21h6M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V17h5v-1.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "chart": '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    "coins": '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="8" ry="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>',
    "flask": '<svg viewBox="0 0 24 24"><path d="M9 3h6M10 3v6l-5.5 9.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.5L14 9V3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "flag": '<svg viewBox="0 0 24 24"><path d="M5 21V4m0 0h12l-2 4 2 4H5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "alert": '<svg viewBox="0 0 24 24"><path d="M12 3 2 20h20L12 3zM12 10v4M12 17v1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "target": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="1" fill="currentColor"/></svg>',
    "users": '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 5a3.5 3.5 0 0 1 0 7M18 13.5a6.5 6.5 0 0 1 3.5 6.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    "book": '<svg viewBox="0 0 24 24"><path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4zM20 4h-6a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h7z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
}

CSS = """
@font-face { font-family: 'Roboto'; src: url('file://%(f)s/Roboto-Regular.ttf'); font-weight: 400; }
@font-face { font-family: 'Roboto'; src: url('file://%(f)s/Roboto-Italic.ttf'); font-weight: 400; font-style: italic; }
@font-face { font-family: 'Roboto'; src: url('file://%(f)s/Roboto-Light.ttf'); font-weight: 300; }
@font-face { font-family: 'Roboto'; src: url('file://%(f)s/Roboto-Medium.ttf'); font-weight: 500; }
@font-face { font-family: 'Roboto'; src: url('file://%(f)s/Roboto-Bold.ttf'); font-weight: 700; }
@page { size: A4; margin: 15mm 14mm 16mm 14mm;
  @bottom-left { content: string(startup) "  ·  " string(doctitle); font: 7.5pt 'Roboto', sans-serif; color: #9CA3AF; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 7.5pt 'Roboto', sans-serif; color: #9CA3AF; } }
@page landscape { size: A4 landscape; margin: 10mm 12mm 12mm 12mm; }
@page first { margin-top: 12mm; }
html { font-family: 'Roboto', 'Liberation Sans', sans-serif; font-size: 9.4pt; color: %(ink)s; line-height: 1.36; }
body { margin: 0; }
h1, h2, h3 { margin: 0; color: %(ink)s; page-break-after: avoid; font-weight: 700; }
p { margin: 0 0 5pt 0; }
b { font-weight: 700; }
.page-first { page: first; }
.landscape { page: landscape; page-break-before: always; page-break-after: always; }
.masthead { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8pt; }
.masthead .name { font-size: 24pt; font-weight: 700; letter-spacing: -0.4pt; string-set: startup content(); }
.masthead .sub { text-align: right; font-size: 8.6pt; color: %(muted)s; }
.masthead .sub .t { string-set: doctitle content(); font-weight: 500; color: %(ink)s; }
.scope { font-size: 7.4pt; color: #9CA3AF; margin-bottom: 8pt; }
.hero { display: flex; border-radius: 8pt; overflow: hidden; margin-bottom: 9pt; page-break-inside: avoid; border: 0.8pt solid %(line)s; }
.hero .badge { flex: 0 0 34mm; color: #fff; display: flex; flex-direction: column; justify-content: center; padding: 8pt 8pt; }
.hero .badge .k { font-size: 6.8pt; text-transform: uppercase; letter-spacing: 1pt; opacity: .85; margin-bottom: 3pt; }
.hero .badge .v { font-size: 13pt; font-weight: 700; line-height: 1.15; }
.hero .txt { padding: 7pt 10pt; font-size: 9.3pt; line-height: 1.38; background: #fff; }
.hero .conds { margin-top: 4pt; font-size: 8.6pt; } .hero .conds ol { margin: 2pt 0 0 0; padding-left: 14pt; } .hero .conds li { margin-bottom: 1pt; }
.kill { font-size: 8.4pt; background: %(soft)s; border-radius: 4pt; padding: 4pt 8pt; margin: -3pt 0 8pt 0; }
.tile .hint { font-size: 6pt; color: %(muted)s; line-height: 1.15; margin-top: 3pt; }
.sec-h { display: flex; align-items: center; gap: 6pt; margin: 5pt 0 5pt 0; }
.sec-h h2 { font-size: 11pt; }
.sec-h .ic { width: 12pt; height: 12pt; color: %(market)s; }
.sec-h .ic svg { width: 12pt; height: 12pt; }
h1.sec { font-size: 15pt; margin: 4pt 0 3pt 0; }
.sec-top { display: flex; align-items: center; gap: 8pt; margin: 12pt 0 8pt 0; padding-bottom: 5pt; border-bottom: 1.2pt solid %(line)s; page-break-after: avoid; }
.sec-top .ic { width: 20pt; height: 20pt; border-radius: 10pt; background: %(soft2)s; color: %(market)s; display: flex; align-items: center; justify-content: center; }
.sec-top .ic svg { width: 12pt; height: 12pt; }
.timeline { position: relative; margin: 0 0 6pt 0; padding: 0; list-style: none; }
.timeline li { position: relative; padding: 0 0 4pt 20pt; font-size: 9.2pt; }
.timeline li::before { content: attr(data-n); position: absolute; left: 0; top: 1pt; width: 13pt; height: 13pt; border-radius: 7pt; background: %(market)s; color: #fff; font-size: 7.4pt; font-weight: 700; text-align: center; line-height: 13pt; }
.timeline li::after { content: ""; position: absolute; left: 6pt; top: 15pt; bottom: -1pt; width: 1pt; background: %(line)s; }
.timeline li:last-child::after { display: none; }
.evidence { font-size: 7.9pt; color: %(muted)s; margin: 2pt 0 8pt 0; }
.legend { font-size: 7.6pt; color: %(muted)s; margin: 0 0 4pt 0; }
.dot { display: inline-block; width: 6pt; height: 6pt; border-radius: 3pt; margin: 0 2pt 0 0; vertical-align: 0; }
.tiles { display: flex; gap: 5pt; margin-bottom: 9pt; }
.tile { flex: 1; background: %(soft)s; border-radius: 6pt; padding: 6pt 5pt 5pt 5pt; text-align: center; }
.tile .lab { font-size: 6.6pt; color: %(muted)s; line-height: 1.15; margin-bottom: 3pt; min-height: 15pt; }
.tile { display: flex; flex-direction: column; justify-content: flex-start; }
.tile .pair { display: flex; justify-content: center; gap: 5pt; align-items: baseline; }
.tile .a { font-size: 11pt; font-weight: 700; color: %(team)s; white-space: nowrap; }
.tile .b { font-size: 11pt; font-weight: 700; color: %(market)s; white-space: nowrap; }
.tile .sep { color: #C7CAD6; font-size: 9pt; }
.tile .one { font-size: 11pt; font-weight: 700; color: %(ink)s; }
.cmp { width: 100%%; border-collapse: collapse; margin-bottom: 3pt; }
.cmp td { padding: 3.2pt 4pt; border-bottom: 0.6pt solid %(line)s; vertical-align: middle; font-size: 7.8pt; }
.cmp td.dom { width: 21%%; font-weight: 500; }
.cmp td.dom .st { display: block; font-size: 6.6pt; color: %(muted)s; font-weight: 400; }
.cmp td.bar { width: 34%%; }
.cmp td.gap { width: 8%%; text-align: center; font-weight: 700; }
.cmp td.eff { width: 37%%; font-size: 7.2pt; color: #374151; }
.rb { display: flex; align-items: center; gap: 4pt; height: 16pt; }
.rb .lo, .rb .hi { flex: 0 0 26pt; font-size: 6.4pt; color: %(muted)s; white-space: nowrap; }
.rb .lo { text-align: right; }
.rb .tr { flex: 1; position: relative; height: 16pt; }
.rb .track { position: absolute; left: 0; right: 0; top: 6pt; height: 5pt; border-radius: 3pt; background: %(line)s; }
.rb .band { position: absolute; top: 6pt; height: 5pt; border-radius: 3pt; background: %(market)s; opacity: .55; }
.rb .mark { position: absolute; top: 3.5pt; width: 10pt; height: 10pt; margin-left: -5pt; border-radius: 5pt; background: %(team)s; border: 1.6pt solid #fff; box-shadow: 0 0 0 0.6pt %(team)s; }
.rb .mid { position: absolute; top: -2pt; font-size: 6.2pt; color: %(market)s; margin-left: -10pt; }
.cmp td.eff .effl { font-size: 6.4pt; color: %(muted)s; text-transform: uppercase; letter-spacing: .5pt; margin-bottom: 1.5pt; }
.cmp td.eff .chip { margin: 0 2pt 2pt 0; font-size: 7pt; }
.filled { background: %(soft)s; border-radius: 6pt; padding: 6pt 8pt; margin: 4pt 0 4pt 0; }
.filled .fl { font-size: 7.4pt; font-weight: 700; color: %(ink)s; margin-bottom: 4pt; }
.filled .fchips { display: flex; flex-wrap: wrap; }
.fchip { display: inline-block; background: #fff; border: 0.6pt solid %(line)s; border-radius: 5pt; padding: 2.5pt 6pt; margin: 0 4pt 4pt 0; font-size: 7.6pt; white-space: nowrap; }
.fchip .rng { color: %(muted)s; }
.filled .fnote { font-size: 7pt; color: %(muted)s; margin-top: 1pt; }
.spread { display: flex; gap: 5pt; margin-bottom: 4pt; }
.spread .sp { flex: 1; border: 0.7pt solid %(line)s; border-radius: 6pt; padding: 5pt 7pt; }
.spread .sph { font-size: 7.4pt; font-weight: 700; text-transform: uppercase; letter-spacing: .4pt; margin-bottom: 3pt; }
.spread .spr { display: flex; justify-content: space-between; font-size: 7.6pt; padding: 1.5pt 0; border-top: 0.5pt solid %(line)s; }
.spread .spl { color: %(muted)s; } .spread .spv { font-weight: 700; }
.note { font-size: 7.8pt; color: #9CA3AF; margin: 2pt 0 6pt 0; }
.lead { font-size: 10.8pt; font-weight: 500; color: %(ink)s; margin: 0 0 7pt 0; line-height: 1.34; }
.body { font-size: 9.4pt; }
.card { border: 0.8pt solid %(line)s; border-radius: 7pt; padding: 8pt 10pt 6pt 10pt; margin: 0 0 8pt 0; page-break-inside: avoid; }
.card .hd { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 5pt; }
.card h3 { font-size: 10.6pt; }
.card .chips { font-size: 7.6pt; }
.chip { display: inline-block; border-radius: 9pt; padding: 1.5pt 6pt; font-size: 7.4pt; font-weight: 500; white-space: nowrap; }
.chip.team { background: #FDEBD8; color: #9A4B00; } .chip.market { background: %(soft2)s; color: #2A36A0; }
.chip.grey { background: %(soft)s; color: #4B5563; } .chip.good { background: #DCFCE7; color: #166534; } .chip.bad { background: #FEE2E2; color: #991B1B; } .chip.warn { background: #FEF3C7; color: #92400E; }
.grid2 { display: flex; flex-wrap: wrap; justify-content: space-between; }
.grid2 .cell { width: 48.6%%; box-sizing: border-box; margin-bottom: 5pt; background: %(soft)s; border-radius: 5pt; padding: 5pt 7pt; }
.cell .cl { display: flex; align-items: center; gap: 4pt; font-size: 7.4pt; font-weight: 700; text-transform: uppercase; letter-spacing: .5pt; color: %(market)s; margin-bottom: 2pt; }
.cell .cl svg { width: 9pt; height: 9pt; }
.cell p { font-size: 8.6pt; margin: 0; }
.bignums { display: flex; gap: 6pt; margin: 0 0 8pt 0; }
.bignums .bn { flex: 1; border-radius: 6pt; padding: 7pt 8pt; background: %(soft)s; }
.bignums .bn .v { font-size: 15pt; font-weight: 700; line-height: 1.1; }
.bignums .bn .l { font-size: 7.2pt; color: %(muted)s; margin-top: 2pt; }
.bignums .bn .c { font-size: 7.2pt; margin-top: 2pt; }
.bn.market .v { color: %(market)s; } .bn.team .v { color: %(team)s; }
.chart { text-align: center; margin: 3pt 0 6pt 0; page-break-inside: avoid; }
.chart img { max-width: 100%%; }
.fin-row { display: flex; gap: 10pt; margin-bottom: 6pt; }
.fin-c { flex: 1; min-width: 0; }
.fin-h { font-size: 10.5pt; font-weight: 700; margin: 4pt 0 6pt 0; }
.flags-intro { font-size: 8pt; color: %(muted)s; margin: 0 0 5pt 0; }
table.flags td { vertical-align: middle; }
.lamp { display: inline-block; width: 8pt; height: 8pt; border-radius: 4pt; margin-right: 4pt; vertical-align: -0.5pt; }
.lamp.green { background: #16A34A; } .lamp.amber { background: #D97706; } .lamp.red { background: #DC2626; }
.cap-p { font-size: 8.2pt; line-height: 1.35; margin: 6pt 0 4pt 0; }
table.flags th, table.flags td { font-size: 7.6pt; padding: 2.6pt 4pt; }
.landscape h1.sec { margin-top: 0; margin-bottom: 4pt; }
table.t { border-collapse: collapse; width: 100%%; margin: 0 0 6pt 0; page-break-inside: avoid; }
table.t.long { page-break-inside: auto; }
table.t tr { page-break-inside: avoid; }
table.t th { background: %(soft2)s; color: %(ink)s; font-weight: 700; text-align: left; padding: 3.5pt 5pt; font-size: 7.4pt; border-bottom: 1pt solid #C7CAD6; }
table.t td { padding: 3pt 5pt; border-bottom: 0.6pt solid %(line)s; vertical-align: top; font-size: 7.8pt; }
table.t tr.self td { background: #FFF4E5; font-weight: 500; }
table.comp th, table.comp td { font-size: 7.4pt; }
.dims { display: flex; gap: 6pt; margin: 0 0 7pt 0; }
.dims .d { flex: 1; background: %(soft)s; border-radius: 6pt; padding: 6pt 8pt; }
.dims .d .n { font-size: 6.6pt; color: %(muted)s; text-transform: uppercase; letter-spacing: .6pt; }
.dims .d .l { font-size: 9.2pt; font-weight: 700; margin: 1pt 0 2pt 0; }
.dims .d .w { font-size: 7.8pt; color: #374151; }
.step { display: flex; gap: 8pt; margin-bottom: 7pt; page-break-inside: avoid; border: 0.8pt solid %(line)s; border-radius: 7pt; padding: 7pt 9pt; }
.step .num { flex: 0 0 19pt; height: 19pt; border-radius: 10pt; background: %(market)s; color: #fff; font-weight: 700; text-align: center; line-height: 19pt; font-size: 10pt; }
.step .txt { flex: 1; }
.step h3 { font-size: 10.2pt; margin-bottom: 2pt; }
.step p { font-size: 9pt; margin-bottom: 2pt; }
.step .thr { background: %(soft2)s; border-radius: 5pt; padding: 3.5pt 7pt; margin-top: 3pt; font-size: 8.6pt; }
.step .thr b { color: %(market)s; }
.risk { border: 0.8pt solid %(line)s; border-radius: 7pt; padding: 7pt 9pt 5pt 9pt; margin-bottom: 7pt; page-break-inside: auto; }
.risk .hd, .risk .what { page-break-after: avoid; } .risk .row { page-break-inside: avoid; }
.risk .hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4pt; }
.risk h3 { font-size: 10pt; }
.risk .what { font-size: 8.8pt; margin-bottom: 4pt; }
.risk .row { display: flex; gap: 6pt; }
.risk .row .c { flex: 1; background: %(soft)s; border-radius: 5pt; padding: 4pt 6pt; }
.risk .row .c .cl { font-size: 6.8pt; font-weight: 700; text-transform: uppercase; letter-spacing: .5pt; color: %(market)s; margin-bottom: 1pt; }
.risk .row .c p { font-size: 8.2pt; margin: 0; }
.appendix h2.sec { font-size: 11pt; margin: 10pt 0 4pt 0; }
.grey { color: %(muted)s; } .small { font-size: 8.2pt; }
.linehead { font-size: 8.4pt; color: %(muted)s; margin: 4pt 0 2pt 0; }
"""


def _img(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _table(rows, cls="", self_mark=None, widths=None):
    if not rows: return ""
    out = [f'<table class="t {cls}">']
    if widths: out.append("<colgroup>" + "".join(f'<col style="width:{w}%">' for w in widths) + "</colgroup>")
    out.append("<thead><tr>" + "".join(f"<th>{E(str(c))}</th>" for c in rows[0]) + "</tr></thead><tbody>")
    for r in rows[1:]:
        cls_r = ' class="self"' if self_mark and str(r[0]).endswith(self_mark) else ""
        out.append(f"<tr{cls_r}>" + "".join(f"<td>{E(str(c))}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _mk(c_, cur):
    return _dv(c_["kind"], c_["market"], cur) + (f" [{_dv(c_['kind'], c_['market_low'], cur)}–{_dv(c_['kind'], c_['market_high'], cur)}]" if c_["market_low"] != c_["market_high"] else "")


def _mstat(c_, T):
    """'named source' / 'benchmark library' / 'analyst's estimate' plus library flags — where the market number comes from."""
    s = T["market_status"].get(c_.get("market_status") or "", "")
    fl = [T["lib_flag"][f] for f in (c_.get("library_flags") or []) if f in T["lib_flag"]]
    return s + (" (" + "; ".join(fl) + ")" if fl else "")


def _sec(T_title, icon):
    return f'<div class="sec-top" id="s-{icon}"><div class="ic">{ICON[icon]}</div><h1 class="sec">{E(T_title)}</h1></div>'


def _range_bar(c_, cur, T):
    """Market band (low–high) on a grey track, the team's number as an orange dot; labels under the ends."""
    f, lo, hi = c_["founder"], c_["market_low"], c_["market_high"]
    if lo is None or hi is None or f is None:
        return f'<span class="chip grey">{E(T["fill"]["unverified"])}</span>'
    a, b = min(lo, f), max(hi, f)
    span = (b - a) or abs(b) or 1.0
    pad = span * 0.08
    if f < lo: a -= max(pad, (lo - f) * 0.6)   # the team's number sits clearly outside the band, not on its edge
    if f > hi: b += max(pad, (f - hi) * 0.6)
    a -= pad; b += pad; span = b - a
    pct = lambda v: max(0.0, min(100.0, (v - a) / span * 100))
    filled = c_["fill"] == "filled_from_market"
    mark = "" if filled else f'<div class="mark" style="left:{pct(f):.1f}%"></div>'
    mid = f'<div class="mid" style="left:{pct(c_["market"]):.1f}%">{E(_dv(c_["kind"], c_["market"], cur))}</div>'
    return (f'<div class="rb"><div class="lo">{E(_dv(c_["kind"], lo, cur))}</div><div class="tr"><div class="track"></div>'
            f'<div class="band" style="left:{pct(lo):.1f}%;width:{max(1.5, pct(hi) - pct(lo)):.1f}%"></div>{mid}{mark}</div>'
            f'<div class="hi">{E(_dv(c_["kind"], hi, cur))}</div></div>')


def _sev(v):
    return {"High": "bad", "Medium": "warn", "Low": "good", "Reversible": "good", "Structural": "bad", "Unknown": "grey"}.get(v, "grey")


def financial_picture(model, rep, T, cur, screen=False):
    """P&L, cumulative cash, capital waterfall and the signal strip — inline SVG from model.json (combined for multi-line).
    Print: two columns on a landscape page. Screen: charts full width, one under the other, signals in a row."""
    from svg_charts import capital_chart, capital_sentence, cash_chart, flags_html, pl_chart
    from build_report import round_text
    cases, br, cmp_rows, n, comb, lname = lead(model, rep)
    L = T["fin"]; src = comb if comb else model["cases"]
    cvr = model.get("capital_vs_round")
    ue = cases["market"]["unit_economics"]
    rphrase = round_text(model, cur, T) if cvr and cvr.get("position") in ("below_round", "inside_round", "above_round") else ""
    cap_p = f'<p class="cap-p">{E(capital_sentence(src["market"], cvr, cur, L, rphrase))}</p>'
    flags = f'<div class="fin-h">{E(L["flags_title"])}</div>' + flags_html(ue, src["market"]["breakeven_month"], n, cvr, L, rphrase)
    if screen:
        return (f'<div class="fin"><div class="fin-c">{pl_chart(src["market"], src["founder"], cur, L, W=980, H=420)}</div><div class="fin-c">{cash_chart(src, cur, L, W=980, H=420)}</div>'
                f'<div class="fin-c">{capital_chart(src["market"], cvr, cur, L, W=980, H=400)}{cap_p}</div><div class="fin-c">{flags}</div></div>')
    return (f'<div class="fin"><div class="fin-row"><div class="fin-c">{pl_chart(src["market"], src["founder"], cur, L, H=330)}</div><div class="fin-c">{cash_chart(src, cur, L, H=330)}</div></div>'
            f'<div class="fin-row"><div class="fin-c">{capital_chart(src["market"], cvr, cur, L, H=290)}{cap_p}</div><div class="fin-c">{flags}</div></div></div>')


def render_pdf(rep, T, cur, model, charts_dir, out_path):
    from weasyprint import HTML
    HTML(string=render_html(rep, T, cur, model, charts_dir), base_url=charts_dir).write_pdf(out_path)


def render_html(rep, T, cur, model, charts_dir, screen=False):
    """The report as one self-contained HTML document. screen=False → print stylesheet (what the PDF is made of);
    screen=True → the interactive page: sticky section nav, responsive layout, collapsible appendix, series toggles."""
    cases, br, cmp_rows, n, comb, lname = lead(model, rep)
    lines_iter = list(model["lines"].items()) if comb else [(None, model)]
    measured = model.get("mode") == "measured"
    H = []; a = H.append
    team_lbl, market_lbl = T["founder"], T["market"]

    # ── page 1
    a('<div class="page-first">')
    a(f'<div class="masthead"><div class="name">{E(rep["startup"])}</div><div class="sub"><span class="t">{E(T["title_suffix"])}</span><br>{E(str(rep.get("date", "")))}</div></div>')
    a(f'<div class="scope">{E(T["scope_note"])}</div>')
    a(f'<div class="hero"><div class="badge" style="background:#{VERDICT_COLORS[rep["verdict"]]}"><div class="k">{E(T["verdict_k"])}</div>'
      f'<div class="v">{E(T["verdict_names"][rep["verdict"]])}</div></div><div class="txt"><div>{E(rep["verdict_text"])}</div>'
      + (f'<div class="conds"><b>{E(T["need_k"] if rep["verdict"] == "Not assessable" else T["cond_k"])}:</b><ol>' + "".join(f"<li>{E(x)}</li>" for x in rep.get("conditions") or []) + "</ol></div>" if rep.get("conditions") else "")
      + "</div></div>")
    kc = rep.get("kill_criterion")
    if kc: a(f'<div class="kill"><b>{E(T["kill_k"])}:</b> {E(kc["metric"])} — {E(kc["threshold"])}. <span class="grey">{E(T["kill_model"])}: {E(kc["what_model_shows"])}</span></div>')
    a(f'<div class="sec-h"><div class="ic">{ICON["book"]}</div><h2>{E(T["story"])}</h2></div><ol class="timeline">' + "".join(f'<li data-n="{i}">{E(s)}</li>' for i, s in enumerate(rep["story"], 1)) + "</ol>")
    a(f'<div class="evidence"><b>{E(T["evidence_basis"])}:</b> {E(rep["evidence_basis"])}</div>')
    kpis = rep.get("kpis") or default_kpis(model, rep, T)
    a(f'<div class="legend"><span class="dot" style="background:{TEAM}"></span>{E(team_lbl)} &nbsp;&nbsp; <span class="dot" style="background:{MARKET}"></span>{E(market_lbl)}</div>')
    tiles = []
    for k in kpis:
        lab = k["label"].split(" — ")[0]
        if "pair" in k:
            va, vb = (fmt_value(get_ref(model, r), k["fmt"], cur, T) for r in k["pair"])
            tiles.append(f'<div class="tile"><div class="lab">{E(lab)}</div><div class="pair"><span class="a">{E(va)}</span><span class="sep">|</span><span class="b">{E(vb)}</span></div><div class="hint">{E(k.get("hint", ""))}</div></div>')
        else:
            tiles.append(f'<div class="tile"><div class="lab">{E(k["label"])}</div><div class="one">{E(fmt_value(get_ref(model, k["ref"]), k.get("fmt", "text"), cur, T))}</div></div>')
    a('<div class="tiles">' + "".join(tiles) + "</div>")
    a(f'<div class="sec-h"><div class="ic">{ICON["target"]}</div><h2>{E(T["comparison"])}</h2></div>')
    notes = (rep.get("comparison") or {}).get("notes") or {}
    src_rows, key_ = _bridge_rows(model)
    rank = {(x["line"], x["domain"]): x[key_]["delta"] for x in src_rows} if comb else None
    pairs = []
    for ln, r_ in lines_iter:
        gen = gen_comparison(r_["comparison"], (r_["bridge_to_market"] if measured else r_["bridge"]), T, cur, notes, line=ln, rank=rank, measured=measured)
        pairs += list(zip(r_["comparison"], gen, [ln] * len(gen)))
    pairs.sort(key=lambda x: -x[1][5])
    real = [x for x in pairs if x[0]["fill"] != "filled_from_market"]
    filled = [x for x in pairs if x[0]["fill"] == "filled_from_market"]
    eff_ix = {}
    for ln, r_ in lines_iter:
        for b in (r_["bridge_to_market"] if measured else r_["bridge"]): eff_ix[(ln, b["domain"])] = b
    n1 = page1_rows(rep)
    real.sort(key=lambda x: x[0]["domain"] in COST_DOMAINS)   # team cost last: a plan input, not a market disagreement
    shown = real[:n1]
    if shown:
        a('<table class="cmp"><tbody>')
        for c_, g, ln in shown:
            st = T["status"].get(c_["status"], c_["status"]); fl = T["fill"].get(c_["fill"], "") if c_["fill"] else ""
            st_txt = f"{st}{' · ' + fl if fl else ''}"
            f_chip = f'<span class="chip team">{E(_dv(c_["kind"], c_["founder"], cur))}</span>'
            st_txt += " · " + _mstat(c_, T)
            b = eff_ix.get((ln, c_["domain"]))
            chips = []
            if b and not measured:
                cap = b["peak_capital_need"]; be_ = b["breakeven_month"]; lc = b.get("ltv_cac") or {}
                chips.append(f'<span class="chip {"good" if cap["delta"] < 0 else ("bad" if cap["delta"] > 0 else "grey")}">{E(T["cap_short"])}: {E(money(cap["market"], cur))} → {E(money(cap["if_founder_right"], cur))}</span>')
                bm, bf = be_["market"], be_["if_founder_right"]
                cls = "grey" if bm == bf else ("good" if (bf or 999) < (bm or 999) else "bad")
                chips.append(f'<span class="chip {cls}">{E(T["be_short"])}: {mlabel(bm) if bm else E(T["none"])} → {mlabel(bf) if bf else E(T["none"])}</span>')
                if lc.get("market") is not None and lc.get("if_founder_right") is not None:
                    chips.append(f'<span class="chip {"good" if lc["if_founder_right"] > lc["market"] else "bad"}">LTV/CAC {lc["market"]:.1f} → {lc["if_founder_right"]:.1f}</span>')
            elif b:
                rv = b["revenue_end"]
                chips.append(f'<span class="chip {"good" if rv["delta"] > 0 else "bad"}">{E(T["rev_short"])}: {E(money(rv["measured"], cur))} → {E(money(rv["if_at_category"], cur))}</span>')
            eff_html = (f'<div class="effl">{E(T["if_right"]) if not measured else ""}</div>' if chips else "") + " ".join(chips) if chips else "—"
            a(f'<tr><td class="dom">{E(g[0])} {f_chip}<span class="st">{E(st_txt)}</span></td><td class="bar">{_range_bar(c_, cur, T)}</td><td class="gap">{E(g[3])}</td><td class="eff">{eff_html}</td></tr>')
        a("</tbody></table>")
    if filled and len(shown) < n1:
        chips = []
        for c_, g, ln in filled:
            tag = T["market_status"].get(c_.get("market_status") or "", ""); star = "*" if c_.get("library_flags") else ""
            chips.append(f'<span class="fchip"><b>{E(g[0])}</b> {E(_dv(c_["kind"], c_["market"], cur))} <span class="rng">[{E(_dv(c_["kind"], c_["market_low"], cur))}–{E(_dv(c_["kind"], c_["market_high"], cur))}] · {E(tag)}{star}</span></span>')
        flagged = any(c_.get("library_flags") for c_, _, _ in filled)
        a(f'<div class="filled"><div class="fl"><span class="dot" style="background:{MARKET}"></span>{E(T["cmp_filled"])}</div><div class="fchips">{"".join(chips)}</div><div class="fnote">{E(T["cmp_filled_note"])}{(" * " + E(T["lib_flag_note"])) if flagged else ""}</div></div>')
    rest = len(real) - len(shown)
    if rest > 0: a(f'<p class="note">{E(T["cmp_more"].format(n=rest))}</p>')
    if len(shown) <= 2 and not (rep.get("conditions") and not screen):   # room left on page 1 (print): the spread of outcomes across the market edges
        rows_o = gen_outcomes(model, rep, T, cur)
        want = [T["sc_be"], T["sc_cap"]]
        rev_row = next((r for r in rows_o[1:] if r[0] == T["sc_rev"].format(n=n)), None)
        picked = [r for r in rows_o[1:] if r[0] in want] + ([rev_row] if rev_row else [])
        cols = [("pessimistic", 3, PESS_C), ("market", 2, MARKET), ("founder", 1, TEAM), ("optimistic", 4, OPT_C)]
        a(f'<div class="sec-h" style="margin-top:6pt"><div class="ic">{ICON["chart"]}</div><h2>{E(T["market_range"])}</h2></div><div class="spread">')
        for ck, ci, col in cols:
            a(f'<div class="sp"><div class="sph" style="color:{col}">{E(T[ck])}</div>' + "".join(f'<div class="spr"><span class="spl">{E(r[0])}</span><span class="spv">{E(r[ci])}</span></div>' for r in picked) + "</div>")
        a("</div>")
    a("</div>")

    # ── page 2: dashboard
    a(f'<div class="landscape" id="s-fin"><h1 class="sec">{E(T["dashboard"])}</h1>' + financial_picture(model, rep, T, cur, screen) + f'<p class="note">{E(T["dashboard_note"])}</p></div>')

    # ── assumptions
    a(_sec(T["assumptions"], "bulb") + f'<p class="lead">{E(rep["assumptions"]["lead"])}</p>')
    from svg_charts import bridge_chart
    src_b, key_b = _bridge_rows(model)
    bsvg = bridge_chart(src_b, cur, T["fin"], T["dom"], measured=measured, W=980)
    if bsvg: a(f'<div class="chart bridge">{bsvg}</div>')
    from svg_charts import tornado_chart
    tor_rows = model.get("tornado") or (next(iter(model["lines"].values()))["tornado"] if comb else [])
    tsvg = tornado_chart(tor_rows, cases["market"]["peak_capital_need"] if not comb else comb["market"]["peak_capital_need"], cur, T["fin"], T["dom"], W=980) if not comb else ""
    if tsvg: a(f'<div class="chart tornado">{tsvg}</div>')
    cmp_ix = {(ln, c_["domain"]): c_ for ln, r_ in lines_iter for c_ in r_["comparison"]}
    order = {key: i for i, key in enumerate(top_bridge_domains(model, rep, k=99))}
    stories = sorted(rep["assumptions"]["stories"], key=lambda s_: order.get((s_.get("line") if comb else None, s_["domain"]), 999))
    for s_ in stories:
        key = (s_.get("line") if comb else None, s_["domain"]); c_ = cmp_ix.get(key)
        title = T["dom"].get(s_["domain"], s_["domain"]).capitalize() + (f" — {key[0]}" if key[0] else "")
        chips = f'<span class="chip team">{E(team_lbl)}: {E(_dv(c_["kind"], c_["founder"], cur))}</span> <span class="chip market">{E(market_lbl)}: {E(_mk(c_, cur))}</span>' if c_ else ""
        a(f'<div class="card"><div class="hd"><h3>{E(title)}</h3><div class="chips">{chips}</div></div><div class="grid2">')
        for lab, fld, ic in (("st_believes", "belief", "bulb"), ("st_evidence", "evidence", "chart"), ("st_stakes", "stakes", "coins"), ("st_test", "test", "flask")):
            a(f'<div class="cell"><div class="cl">{ICON[ic]}{E(T[lab])}</div><p>{E(s_[fld])}</p></div>')
        a("</div></div>")

    # ── big numbers helper (break-even, capital, revenue at the end) for a case
    def bignums(case_key, cls):
        ks = kpis[2:5] if len(kpis) >= 5 and all("pair" in k for k in kpis[2:5]) else []
        out = []
        for k in ks:
            ref = k["pair"][0 if case_key == "founder" else 1]
            out.append(f'<div class="bn {cls}"><div class="v">{E(fmt_value(get_ref(model, ref), k["fmt"], cur, T))}</div><div class="l">{E(k["label"].split(" — ")[0])}</div></div>')
        return f'<div class="bignums">{"".join(out)}</div>' if out else ""

    # ── market case
    a(_sec(T["market_case"], "chart") + f'<p class="lead">{E(rep["market_case"]["lead"])}</p>' + bignums("market", "market"))
    for p_ in rep["market_case"]["paragraphs"]: a(f'<p class="body">{E(p_)}</p>')
    from svg_charts import lines_chart
    src_c = comb if comb else model["cases"]
    a(f'<div class="chart">{lines_chart(src_c, "mrr", T["fin"]["rev_m"], cur, T["fin"], W=980 if screen else 700, H=360)}</div>')
    rows = gen_outcomes(model, rep, T, cur)
    a(_table([[rows[0][0], T["market"], T["market_range"]]] + [[r[0], r[2], f"{r[3]} / {r[4]}"] for r in rows[1:]], widths=[42, 24, 34]))
    a(f'<p class="note">{E(T["market_range_note"])}</p>')

    # ── founder case
    a(_sec(T["founder_case"], "users") + f'<p class="lead">{E(rep["founder_case"]["lead"])}</p>' + bignums("founder", "team"))
    for p_ in rep["founder_case"]["paragraphs"]: a(f'<p class="body">{E(p_)}</p>')
    for ln, r_ in lines_iter:
        ue = gen_unit_economics(r_["cases"], T, cur, (f"{T['line']}: {ln}" if ln else T["ue_title"]))
        a(_table([[ue[0][0], T["founder"], T["market"]]] + [[r[0], r[1], r[2]] for r in ue[1:]], widths=[48, 26, 26]))

    # ── competition
    cp = rep["competition"]; dims = cp["dimensions"]
    a(_sec(T["competition"], "target") + f'<p class="lead">{E(cp["lead"])}</p>')
    a('<div class="dims">' + "".join(f'<div class="d"><div class="n">{E(T["dims_intro"])} · {i}</div><div class="l">{E(dm["label"])}</div><div class="w">{E(dm["why"])}</div></div>' for i, dm in enumerate(dims, 1)) + "</div>")
    hdr = [T["col_product"], T["col_layer"], T["col_price"]] + [dm["label"] for dm in dims] + [T["col_source"]]
    nd = len(dims); wd = [14, 11, 13] + [round((100 - 14 - 11 - 13 - 12) / nd)] * nd + [12]
    out = [f'<table class="t comp long"><colgroup>' + "".join(f'<col style="width:{w}%">' for w in wd) + "</colgroup><thead><tr>" + "".join(f"<th>{E(c)}</th>" for c in hdr) + "</tr></thead><tbody>"]
    lay_cls = {"direct": "market", "indirect": "warn", "displacer": "bad"}
    for r_ in sorted(cp["rows"], key=lambda x: (not x.get("self"), ("direct", "indirect", "displacer").index(x["layer"]))):
        name = E(r_["name"]) + (f' <span class="chip team">{E(T["self_mark"])}</span>' if r_.get("self") else "")
        tr_cls = ' class="self"' if r_.get("self") else ""
        out.append(f'<tr{tr_cls}><td>{name}</td><td><span class="chip {lay_cls[r_["layer"]]}">{E(T["layer_short"][r_["layer"]])}</span></td><td><b>{E(r_["price"])}</b></td>'
                   + "".join(f"<td>{E(r_['cells'][dm['key']])}</td>" for dm in dims) + f'<td class="grey">{E(r_["source"])}</td></tr>')
    out.append("</tbody></table>"); a("".join(out))
    for p_ in cp["paragraphs"]: a(f'<p class="body">{E(p_)}</p>')
    a(f'<div class="card" style="background:{SOFT2};border-color:{SOFT2}"><div class="cl" style="font-size:7.4pt;font-weight:700;text-transform:uppercase;letter-spacing:.5pt;color:{MARKET};margin-bottom:2pt">{E(T["where_we_win"])}</div><p style="font-size:9.2pt;margin:0">{E(cp["where_we_win"])}</p></div>')

    # ── next 90 days
    a(_sec(T["next_90"], "flag"))
    for i, x in enumerate(rep["next_90_days"], 1):
        a(f'<div class="step"><div class="num">{i}</div><div class="txt"><h3>{E(x["title"])}</h3><p>{E(x["what"])}</p><p class="grey">{E(x["how"])}</p><div class="thr"><b>{E(T["col_threshold"])}:</b> {E(x["threshold"])}</div></div></div>')

    # ── risks
    a(_sec(T["risks_h"], "alert") + f'<p class="note">{E(T["risks_intro"])}</p>')
    for x in rep["risks"]:
        a(f'<div class="risk"><div class="hd"><h3>{E(x["title"])}</h3><div><span class="chip {_sev(x["likelihood"])}">{E(T["col_likelihood"])}: {E(T["risk_enum"][x["likelihood"]])}</span> '
          f'<span class="chip {_sev(x["reversibility"])}">{E(T["col_reversibility"])}: {E(T["risk_enum"][x["reversibility"]])}</span></div></div><div class="what">{E(x["what"])}</div><div class="row">'
          f'<div class="c"><div class="cl">{E(T["col_what_happens"])}</div><p>{E(x["impact"])}</p></div><div class="c"><div class="cl">{E(T["col_signal"])}</div><p>{E(x["signal"])}</p></div>'
          f'<div class="c"><div class="cl">{E(T["col_action"])}</div><p>{E(x["action"])}</p></div></div></div>')

    # ── appendix
    a('<div class="appendix">' + _sec(T["appendix"], "book"))
    a(f'<h2 class="sec">{E(T["ap_assumptions"])}</h2>')
    for ln, r_ in lines_iter:
        if ln: a(f'<p class="linehead">{E(T["line"])}: {E(ln)}</p>')
        rows_a = [[T["cmp_hdr"][0], T["cmp_hdr"][1], T["cmp_hdr"][2], T["cmp_hdr"][3]]]
        for c_ in r_["comparison"]:
            stt = T["status"].get(c_["status"], c_["status"]); fl = T["fill"].get(c_["fill"], "") if c_["fill"] else ""
            rows_a.append([T["dom"].get(c_["domain"], c_["label"]), f"{_dv(c_['kind'], c_['founder'], cur)} ({stt}{'; ' + fl if fl else ''})", f"{_mk(c_, cur)} · {c_['source'] or T['fill']['unverified']}",
                           "—" if c_["gap_ratio"] is None else ("∞" if isinstance(c_["gap_ratio"], str) else fmt_mult(c_["gap_ratio"]))])
        a(_table(rows_a, "long", widths=[20, 20, 52, 8]))
    a(f'<h2 class="sec">{E(T["ap_evidence"])}</h2>' + _table(rep["appendix"]["evidence"], "long"))
    a(f'<h2 class="sec">{E(T["ap_cases"])}</h2>' + _table(gen_outcomes(model, rep, T, cur), widths=[36, 16, 16, 16, 16]))
    units_lbl = T["fin"]["purch"] if src_c["market"]["projection"][0].get("units_label") == "purchases" else T["fin"]["cust"]
    a(f'<div class="chart">{lines_chart(src_c, "cumulative", T["fin"]["cum"], cur, T["fin"], W=980 if screen else 700, H=340)}</div>')
    a(f'<div class="chart">{lines_chart(src_c, "customers", units_lbl, cur, T["fin"], money=False, W=980 if screen else 700, H=340)}</div>')
    a(f'<h2 class="sec">{E(T["ap_ue"])}</h2>')
    for ln, r_ in lines_iter:
        a(_table(gen_unit_economics(r_["cases"], T, cur, (f"{T['line']}: {ln}" if ln else T["ue_title"])), widths=[36, 16, 16, 16, 16]))
    a(f'<h2 class="sec">{E(T["ap_funnel"])}</h2>')
    for ln, r_ in lines_iter:
        gtext, funnel, cap = gen_growth(r_["cases"], r_["comparison"], T)
        pre = f"{T['line']}: {ln} · " if ln else ""
        a(f'<p class="small grey">{E(pre + gtext)}</p>')
        if len(funnel) > 1: a(_table(funnel, widths=[36, 22, 42]))
        a(f'<p class="small">{E(cap)}</p>')
    for ln, r_ in lines_iter:
        cb = gen_comparable(r_["cases"], T, cur)
        if cb: a(f'<h2 class="sec">{E(T["ap_comparable"] + (f" — {ln}" if ln else ""))}</h2>' + _table(cb, widths=[36, 16, 16, 16, 16]))
    a(f'<h2 class="sec">{E(T["ap_bridge"])}</h2>')
    for ln, r_ in lines_iter:
        if r_["bridge"]:
            if ln: a(f'<p class="linehead">{E(T["line"])}: {E(ln)}</p>')
            a(_table(gen_bridge(r_["bridge"], T, cur, n), "long"))
    be = lambda v: mlabel(v) if v else T["none"]
    if measured:
        a(f'<p class="small grey">{E(T["_measured"]["bridge_intro"])}</p>')
        for ln, r_ in lines_iter:
            btm = r_.get("bridge_to_market") or []
            if btm:
                if ln: a(f'<p class="linehead">{E(T["line"])}: {E(ln)}</p>')
                rows_m = [[T["cmp_hdr"][0], T["bridge_hdr"][1], T["bridge_hdr"][4].replace("{n}", str(n)), T["bridge_hdr"][2], T["bridge_hdr"][3]]]
                for x in btm:
                    rows_m.append([T["dom"].get(x["domain"], x["label"]), f"{_dv(x['kind'], x['measured'], cur)} → {_dv(x['kind'], x['category'], cur)}", f"{money(x['revenue_end']['measured'], cur)} → {money(x['revenue_end']['if_at_category'], cur)}",
                                   f"{money(x['peak_capital_need']['measured'], cur)} → {money(x['peak_capital_need']['if_at_category'], cur)}", f"{be(x['breakeven_month']['measured'])} → {be(x['breakeven_month']['if_at_category'])}"])
                a(_table(rows_m, "long"))
    if comb and comb.get("bridge"):
        a(f'<p class="small grey">{E(T["ap_bridge_comb"])}</p>')
        rows_cb = [[T["line"], T["cmp_hdr"][0], T["bridge_hdr"][1], T["bridge_hdr"][2], T["bridge_hdr"][3]]]
        for x in comb["bridge"]:
            rows_cb.append([x["line"], T["dom"].get(x["domain"], x["label"]), ("—" if x["kind"] == "joint" else f"{_dv(x['kind'], x['market'], cur)} → {_dv(x['kind'], x['founder'], cur)}"),
                            f"{money(x['peak_capital_need']['market'], cur)} → {money(x['peak_capital_need']['if_founder_right'], cur)}", f"{be(x['breakeven_month']['market'])} → {be(x['breakeven_month']['if_founder_right'])}"])
        a(_table(rows_cb, "long"))
    a(f'<h2 class="sec">{E(T["glossary_h"])}</h2>' + _table([[T["col_item"], ""]] + [[t, x] for t, x in T["glossary"]], "long", widths=[24, 76]))
    a(f'<p class="note">{E(T["model_note"])}</p></div>')

    vals = {"f": FONT_DIR, "ink": INK, "muted": MUTED, "line": LINE, "soft": SOFT, "soft2": SOFT2, "team": TEAM, "market": MARKET}
    css = CSS % vals
    body = "".join(H)
    if not screen:
        return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
    # screen version: fonts embedded as data URIs (one portable file), section nav, appendix folded, series toggles
    css = _embed_fonts(_for_screen(css)) + SCREEN_CSS % vals
    nav_items = [("s-fin", T["dashboard"]), ("s-bulb", T["assumptions"]), ("s-chart", T["market_case"]), ("s-users", T["founder_case"]),
                 ("s-target", T["competition"]), ("s-flag", T["next_90"]), ("s-alert", T["risks_h"]), ("s-book", T["appendix"])]
    nav = '<nav class="topnav"><div class="brand">' + E(rep["startup"]) + "</div>" + "".join(f'<a href="#{i}">{E(t)}</a>' for i, t in nav_items) + "</nav>"
    body = body.replace('<div class="appendix" style="page-break-before:always">', f'<details class="appendix"><summary>{E(T["appendix"])}</summary><div class="appendix-body">', 1)
    body = body[:body.rfind("</div>")] + "</div></details>"   # the appendix div is the last block; close details instead
    toggles = (f'<div class="toggles"><span>{E(T["fin"].get("show", "Show"))}:</span>'
               f'<label><input type="checkbox" checked data-s="team"> {E(T["fin"]["team"])}</label>'
               f'<label><input type="checkbox" checked data-s="edges"> {E(T["fin"]["edges"])}</label></div>')
    body = body.replace('<div class="fin">', toggles + '<div class="fin">', 1)
    js = """<script>
document.querySelectorAll('.toggles input').forEach(function(cb){cb.addEventListener('change',function(){
  document.querySelectorAll('.fin [data-series="'+cb.dataset.s+'"]').forEach(function(el){el.style.display=cb.checked?'':'none';});});});
window.addEventListener('scroll',function(){var y=window.scrollY+80,cur=null;document.querySelectorAll('.topnav a').forEach(function(a){var t=document.querySelector(a.getAttribute('href'));if(t&&t.offsetTop<=y)cur=a;a.classList.remove('on');});if(cur)cur.classList.add('on');});
</script>"""
    return (f"<!DOCTYPE html><html lang='{E(str(rep.get('lang', 'en')))}'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{E(rep['startup'])} — {E(T['title_suffix'])}</title><style>{css}</style></head><body>{nav}<main class='wrap'>{body}</main>{js}</body></html>")


def _for_screen(css):
    """The print stylesheet is set in points for A4 density; on screen the same proportions read best about 1.6× larger in px."""
    import re
    css = re.sub(r"@page[^{]*\{[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", css)          # page boxes and running footers are print-only
    return re.sub(r"(-?\d+(?:\.\d+)?)pt\b", lambda m: f"{float(m.group(1)) * 1.6:.1f}px", css)


def _embed_fonts(css):
    """file:// font URLs → data URIs so the HTML is one portable file."""
    import re
    def rep(m):
        path = m.group(1)
        try:
            with open(path, "rb") as f: b = base64.b64encode(f.read()).decode()
            return f"url('data:font/ttf;base64,{b}')"
        except OSError:
            return m.group(0)
    return re.sub(r"url\('file://([^']+)'\)", rep, css)


SCREEN_CSS = """
@media screen {
  html { font-size: 16px; background: #EEF0F5; -webkit-font-smoothing: antialiased; }
  body { margin: 0; }
  .topnav { position: sticky; top: 0; z-index: 10; display: flex; gap: 2px; align-items: center; background: rgba(255,255,255,.96); backdrop-filter: blur(6px); border-bottom: 1px solid %(line)s; padding: 10px 24px; overflow-x: auto; white-space: nowrap; }
  .topnav .brand { font-weight: 700; margin-right: 16px; color: %(market)s; font-size: 15px; }
  .topnav a { text-decoration: none; color: %(muted)s; font-size: 13.5px; padding: 6px 10px; border-radius: 8px; }
  .topnav a.on, .topnav a:hover { background: %(soft2)s; color: %(market)s; }
  /* Reading column: prose is held to ~70–80 characters; exhibits (charts, tables, tiles) may use the full sheet. */
  .wrap { max-width: 920px; margin: 24px auto 80px auto; background: #fff; padding: 44px 64px 64px 64px; border-radius: 18px; box-shadow: 0 2px 12px rgba(20,24,60,.06); }
  .hero, .timeline, .evidence, .scope, .lead, .body, .card, .step, .risk, .lab-p, .filled, .note, .dims, .legend, .toggles, .sec-h, .sec-top, .risks-intro, .small, .linehead { max-width: 700px; }
  .fin, .chart, .cmp, table.t, .tiles, .spread, .bignums, .flags { max-width: 100%%; }
  .page-first, .landscape { page: auto; }
  .masthead { margin-bottom: 14px; }
  .masthead .name { font-size: 40px; }
  .masthead .sub { font-size: 14px; line-height: 1.4; }
  .scope { font-size: 12px; margin-bottom: 18px; }
  .hero { border-radius: 14px; margin-bottom: 22px; }
  .hero .badge { flex: 0 0 230px; padding: 20px 22px; }
  .hero .badge .k { font-size: 11px; letter-spacing: 1.6px; margin-bottom: 6px; }
  .hero .badge .v { font-size: 22px; line-height: 1.18; }
  .hero .txt { padding: 18px 24px; font-size: 16px; line-height: 1.55; display: flex; align-items: center; }
  .hero { max-width: 100%%; } .hero .badge { flex: 0 0 210px; }
  .sec-h { margin: 16px 0 10px 0; } .sec-h h2 { font-size: 20px; } .sec-h .ic, .sec-h .ic svg { width: 20px; height: 20px; }
  .timeline li { font-size: 16px; line-height: 1.55; padding-left: 34px; padding-bottom: 10px; }
  .timeline li::before { width: 22px; height: 22px; border-radius: 11px; font-size: 12px; line-height: 22px; top: 1px; }
  .timeline li::after { left: 10.5px; top: 25px; }
  .evidence { font-size: 13px; margin: 6px 0 18px 0; }
  .legend { font-size: 13px; } .dot { width: 10px; height: 10px; border-radius: 5px; margin-right: 4px; }
  .tiles { gap: 10px; margin-bottom: 22px; flex-wrap: wrap; } .tiles .tile { flex: 1 1 30%%; }
  .tile { border-radius: 12px; padding: 14px 10px 12px 10px; }
  .tile .lab { font-size: 11.5px; min-height: 28px; margin-bottom: 6px; } .tile .a, .tile .b, .tile .one { font-size: 22px; } .tile .sep { font-size: 16px; } .tile .hint { font-size: 11px; line-height: 1.3; margin-top: 6px; }
  .hero .conds { font-size: 14px; margin-top: 8px; } .kill { font-size: 14px; padding: 8px 12px; border-radius: 8px; margin: -6px 0 16px 0; max-width: 700px; }
  .cmp td { padding: 10px 8px; font-size: 14px; } .cmp td.dom .st { font-size: 12px; } .cmp td.eff { font-size: 13px; }
  .rb { height: 30px; } .rb .track, .rb .band { top: 12px; height: 8px; border-radius: 4px; } .rb .mark { top: 7px; width: 18px; height: 18px; margin-left: -9px; border-radius: 9px; border-width: 2.5px; }
  .rb .lo, .rb .hi { flex-basis: 48px; font-size: 12px; } .rb .mid { top: -6px; font-size: 12px; margin-left: -18px; }
  .chip { font-size: 12.5px; padding: 3px 10px; border-radius: 14px; }
  .filled { border-radius: 12px; padding: 14px 16px; margin: 12px 0; } .filled .fl { font-size: 13px; margin-bottom: 8px; } .fchip { font-size: 13px; padding: 5px 10px; border-radius: 8px; margin: 0 8px 8px 0; } .filled .fnote { font-size: 12px; }
  .spread { gap: 12px; } .spread .sp { border-radius: 12px; padding: 12px 14px; } .spread .sph { font-size: 12px; } .spread .spr { font-size: 13.5px; padding: 4px 0; }
  .note { font-size: 13px; margin: 6px 0 14px 0; }
  .landscape { margin-top: 36px; }
  .landscape h1.sec, h1.sec { font-size: 26px; }
  .sec-top { margin: 44px 0 16px 0; padding-bottom: 10px; scroll-margin-top: 70px; } .sec-top .ic { width: 34px; height: 34px; border-radius: 17px; } .sec-top .ic svg { width: 19px; height: 19px; }
  .landscape { scroll-margin-top: 70px; }
  .lead { font-size: 19px; line-height: 1.45; margin-bottom: 14px; }
  .body { font-size: 16px; line-height: 1.62; margin-bottom: 12px; }
  .toggles { display: flex; gap: 18px; align-items: center; font-size: 14px; color: %(muted)s; margin: 6px 0 10px 0; } .toggles label { cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
  .fin .fin-c { margin-bottom: 26px; }
  .fin-h { font-size: 17px; margin: 6px 0 12px 0; }
  .flags-intro { font-size: 14px; max-width: 700px; } .lamp { width: 12px; height: 12px; border-radius: 6px; margin-right: 8px; } .cap-p { font-size: 16px; line-height: 1.6; max-width: 700px; margin: 6px 0 14px 0; }
  .card { border-radius: 14px; padding: 18px 22px 12px 22px; margin-bottom: 16px; } .card h3 { font-size: 18px; } .card .chips { font-size: 13px; }
  .grid2 .cell { border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; } .cell .cl { font-size: 12px; gap: 6px; margin-bottom: 4px; } .cell .cl svg { width: 14px; height: 14px; } .cell p { font-size: 14.5px; line-height: 1.5; }
  .bignums { gap: 12px; margin-bottom: 16px; } .bignums .bn { border-radius: 12px; padding: 14px 16px; } .bignums .bn .v { font-size: 30px; } .bignums .bn .l { font-size: 12.5px; }
  .chart { margin: 8px 0 16px 0; }
  table.t th { font-size: 12.5px; padding: 8px 10px; } table.t td { font-size: 14px; padding: 8px 10px; } table.comp th, table.comp td { font-size: 13px; }
  .dims { gap: 12px; margin-bottom: 14px; } .dims .d { border-radius: 12px; padding: 12px 14px; } .dims .d .n { font-size: 11px; } .dims .d .l { font-size: 15px; } .dims .d .w { font-size: 13.5px; line-height: 1.45; }
  .lab-p { font-size: 15px; }
  .step { border-radius: 14px; padding: 16px 20px; margin-bottom: 12px; gap: 16px; } .step .num { flex-basis: 32px; height: 32px; border-radius: 16px; line-height: 32px; font-size: 16px; } .step h3 { font-size: 18px; margin-bottom: 4px; } .step p { font-size: 15px; line-height: 1.5; } .step .thr { border-radius: 10px; padding: 8px 12px; font-size: 14.5px; }
  .risk { border-radius: 14px; padding: 16px 20px 12px 20px; margin-bottom: 12px; } .risk h3 { font-size: 17px; } .risk .what { font-size: 15px; line-height: 1.5; } .risk .row { gap: 10px; } .risk .row .c { border-radius: 10px; padding: 10px 12px; } .risk .row .c .cl { font-size: 11.5px; } .risk .row .c p { font-size: 14px; line-height: 1.45; }
  details.appendix > summary { cursor: pointer; font-size: 22px; font-weight: 700; color: %(market)s; padding: 18px 0 8px 0; list-style: none; margin-top: 30px; border-top: 1px solid %(line)s; }
  details.appendix > summary::before { content: "▸ "; } details.appendix[open] > summary::before { content: "▾ "; }
  .appendix-body { margin-top: 10px; } .appendix h2.sec { font-size: 18px; margin: 22px 0 8px 0; } .small { font-size: 13px; } .linehead { font-size: 13px; }
  @media (max-width: 820px) { .wrap { padding: 22px 18px; border-radius: 0; margin: 0 0 40px 0; } .tiles, .bignums, .dims, .risk .row, .spread, .fin-row { flex-direction: column; } .tiles, .flags { flex-wrap: wrap; } .grid2 .cell, .flag { width: 100%%; } .hero { flex-direction: column; } .hero .badge { flex-basis: auto; } .masthead { flex-direction: column; align-items: flex-start; gap: 6px; } .masthead .sub { text-align: left; } }
}
"""
