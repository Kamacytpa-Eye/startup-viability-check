"""Inline SVG charts for the report — the financial picture.

Pure Python, no matplotlib: the same SVG is crisp on screen (HTML) and in print (PDF via WeasyPrint), needs no
CDN, and every number in it is read straight from model.json at build time. Three charts + a flag strip:

  pl_chart       monthly P&L — revenue bars, gross-profit and net lines, loss/profit shading, break-even marker
  cash_chart     cumulative cash — market and team lines, the market-edges band, the trough annotated as the
                 capital need, the zero crossing marked
  capital_chart  capital need as a waterfall — payroll + acquisition + other fixed + upfront, minus the gross
                 profit earned before the trough = the need; the typical round for the funding path as a band
  flags          Provify-style traffic lights from cases[*].flags and capital_vs_round

Colours come from chart_style (team orange, market indigo, red / green edges).
"""
import html

from chart_style import COL, GRID, INK, MUTED, fmt_money

E = html.escape
CM, CF, CO, CP = COL["market"], COL["founder"], COL["optimistic"], COL["pessimistic"]
FONT = "Roboto, 'Liberation Sans', sans-serif"
LOSS, PROFIT, BAND = "#FDE2E2", "#DCFCE7", "#E8EAFB"


def _ml(v):
    import chart_style as _cs
    return getattr(_cs, "MFMT", "M{v}").format(v=v)


def _money(x, cur):
    return fmt_money(x, cur)


def _ticks(lo, hi, n=5):
    if hi <= lo: hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** int(f"{raw:e}".split("e")[1])
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    start = int(lo // step) * step
    t = []; v = start
    while v < hi - 1e-9: t.append(v); v += step
    t.append(v)
    return t


class _Ax:
    """A tiny cartesian mapper: data → SVG pixels inside a padded box."""
    def __init__(self, W, H, x0, x1, y0, y1, pad=(58, 12, 46, 60)):   # top right bottom left
        self.W, self.H = W, H; self.t, self.r, self.b, self.l = pad
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
    def X(self, x): return self.l + (x - self.x0) / (self.x1 - self.x0) * (self.W - self.l - self.r)
    def Y(self, y): return self.t + (self.y1 - y) / (self.y1 - self.y0) * (self.H - self.t - self.b)
    def path(self, xs, ys): return "M" + " L".join(f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in zip(xs, ys))
    def grid(self, cur, yticks, xticks, money=True):
        g = []
        for v in yticks:
            g.append(f'<line x1="{self.l}" x2="{self.W - self.r}" y1="{self.Y(v):.1f}" y2="{self.Y(v):.1f}" stroke="{GRID}" stroke-width="1"/>')
            g.append(f'<text x="{self.l - 6}" y="{self.Y(v) + 3.5:.1f}" text-anchor="end" font-size="12" fill="{MUTED}">{E(_money(v, cur) if money else f"{v:g}")}</text>')
        for v in xticks:
            g.append(f'<text x="{self.X(v):.1f}" y="{self.H - self.b + 16}" text-anchor="middle" font-size="12" fill="{MUTED}">{v:g}</text>')
        return "".join(g)


def _wrap(s, n):
    words = s.split(); lines = [""]
    for w in words:
        if len(lines[-1]) + len(w) + 1 > n and lines[-1]: lines.append(w)
        else: lines[-1] = (lines[-1] + " " + w).strip()
    return lines[:2]


def _svg(W, H, body, title=None, subtitle=None):
    head = ""; y = 16
    if title:
        for i, ln in enumerate(_wrap(title, int(W / 9.5))):
            head += f'<text x="0" y="{y}" font-size="16" font-weight="700" fill="{INK}">{E(ln)}</text>'; y += 17
    if subtitle:
        for i, ln in enumerate(_wrap(subtitle, int(W / 6.6))):
            head += f'<text x="0" y="{y - 2}" font-size="11" fill="{MUTED}">{E(ln)}</text>'; y += 13
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="font-family:{FONT};display:block;width:100%;height:auto" role="img">'
            f"{head}{body}</svg>")


def _legend(items, x, y, W=600):
    out = []; cx = x; cy = y - 14 if sum(23 + 6.9 * len(l) + 14 for l, _, _ in items) > W - x else y
    for label, color, kind in items:
        if cx + 23 + 6.9 * len(label) > W - 4: cx = x; cy += 14
        y = cy
        if kind == "line": out.append(f'<line x1="{cx}" x2="{cx + 18}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="2.5"/>')
        elif kind == "dash": out.append(f'<line x1="{cx}" x2="{cx + 18}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="1.6" stroke-dasharray="4 3"/>')
        else: out.append(f'<rect x="{cx}" y="{y - 6}" width="18" height="12" rx="2" fill="{color}"/>')
        out.append(f'<text x="{cx + 23}" y="{y + 4}" font-size="12" fill="{INK}">{E(label)}</text>')
        cx += 23 + 6.9 * len(label) + 14
    return "".join(out)


def pl_chart(case_m, case_f, cur, L, W=600, H=390):
    """Monthly P&L for the market case with the team's net line overlaid. L: labels dict (see LABELS in build_html)."""
    pm, pf = case_m["projection"], case_f["projection"]
    n = len(pm); xs = [r["month"] for r in pm]
    rev = [r["mrr"] for r in pm]; gp = [r["gross_profit"] for r in pm]; net = [r["net_cash_flow"] for r in pm]; netf = [r["net_cash_flow"] for r in pf]
    lo = min(net + netf + [0]); hi = max(rev + [1])
    yt = _ticks(lo * 1.05, hi * 1.08); ax = _Ax(W, H, 0.5, n + 0.5, yt[0], yt[-1])
    xt = [m for m in xs if m % (6 if n > 18 else 3) == 0 or m == 1]
    body = [ax.grid(cur, yt, xt)]
    y0 = ax.Y(0)
    # loss / profit shading under the net line
    body.append(f'<path d="{ax.path(xs, net)} L{ax.X(xs[-1]):.1f},{y0:.1f} L{ax.X(xs[0]):.1f},{y0:.1f} Z" fill="{PROFIT}" opacity="0.9" clip-path="url(#above)"/>')
    body.append(f'<path d="{ax.path(xs, net)} L{ax.X(xs[-1]):.1f},{y0:.1f} L{ax.X(xs[0]):.1f},{y0:.1f} Z" fill="{LOSS}" opacity="0.9" clip-path="url(#below)"/>')
    defs = (f'<defs><clipPath id="above"><rect x="0" y="0" width="{W}" height="{y0:.1f}"/></clipPath>'
            f'<clipPath id="below"><rect x="0" y="{y0:.1f}" width="{W}" height="{H}"/></clipPath></defs>')
    bw = (ax.X(2) - ax.X(1)) * 0.62; LM = E(L["m"])
    for x, v in zip(xs, rev):
        body.append(f'<rect x="{ax.X(x) - bw/2:.1f}" y="{ax.Y(v):.1f}" width="{bw:.1f}" height="{max(0, y0 - ax.Y(v)):.1f}" fill="{CM}" opacity="0.28" rx="1.5"><title>{LM}{x}: {E(_money(v, cur))}</title></rect>')
    body.append(f'<line x1="{ax.l}" x2="{W - ax.r}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{INK}" stroke-width="1"/>')
    body.append(f'<path d="{ax.path(xs, gp)}" fill="none" stroke="{CM}" stroke-width="1.6" stroke-dasharray="5 3"/>')
    body.append(f'<path d="{ax.path(xs, net)}" fill="none" stroke="{CM}" stroke-width="2.6"/>')
    body.append(f'<path d="{ax.path(xs, netf)}" fill="none" stroke="{CF}" stroke-width="2.2" data-series="team"/>')
    for case, be, color, dy in ((case_m, case_m["breakeven_month"], COL["market"], 0), (case_f, case_f["breakeven_month"], COL["founder"], 14)):
        if be:
            body.append(f'<line x1="{ax.X(be):.1f}" x2="{ax.X(be):.1f}" y1="{ax.t + 8}" y2="{H - ax.b}" stroke="{color}" stroke-width="1.2" stroke-dasharray="3 3"/>')
            body.append(f'<text x="{ax.X(be) + 5:.1f}" y="{ax.t + 20 + dy}" font-size="12" font-weight="700" fill="{color}">{E(L["be"])} {_ml(be)}</text>')
    body.append(_legend([(L["rev"], COL["market"], "rect"), (L["gp"], COL["market"], "dash"), (L["net_m"], COL["market"], "line"), (L["net_f"], COL["founder"], "line")], ax.l, H - 6))
    return _svg(W, H, defs + "".join(body), L["pl_title"], L["pl_sub"])


def cash_chart(cases, cur, L, W=600, H=390):
    pm = cases["market"]["projection"]; n = len(pm); xs = [r["month"] for r in pm]
    series = {c: [r["cumulative"] for r in cases[c]["projection"]] for c in cases}
    main = series["market"] + series["founder"] + [0]
    lo_v, hi_v = min(main), max(main)
    edge_lo, edge_hi = min(series["pessimistic"]), max(series["optimistic"])
    y_lo = max(edge_lo, lo_v * 2.2 if lo_v < 0 else -abs(hi_v) * 0.15)
    y_hi = min(edge_hi, min(hi_v * 1.1, max(abs(lo_v) * 3.5, hi_v * 0.3)) if hi_v > 0 else abs(lo_v) * 0.3)   # the trough keeps ≥ 25 % of the height; late months may run off the top (clipped)
    yt = _ticks(y_lo, y_hi); ax = _Ax(W, H, 0.5, n + 0.5, yt[0], yt[-1])
    clip = f'<defs><clipPath id="cashclip"><rect x="{ax.l}" y="{ax.t}" width="{W - ax.l - ax.r}" height="{H - ax.t - ax.b}"/></clipPath></defs>'
    xt = [m for m in xs if m % (6 if n > 18 else 3) == 0 or m == 1]
    body = [clip, ax.grid(cur, yt, xt)]
    lo, hi = series["pessimistic"], series["optimistic"]
    body.append(f'<path d="{ax.path(xs, hi)} {ax.path(xs[::-1], lo[::-1]).replace("M", "L", 1)} Z" fill="{BAND}" opacity="0.9" clip-path="url(#cashclip)" data-series="edges"/>')
    y0 = ax.Y(0)
    body.append(f'<line x1="{ax.l}" x2="{W - ax.r}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{INK}" stroke-width="1"/>')
    body.append(f'<path d="{ax.path(xs, series["founder"])}" fill="none" stroke="{CF}" stroke-width="2.2" data-series="team" clip-path="url(#cashclip)"/>')
    body.append(f'<path d="{ax.path(xs, series["market"])}" fill="none" stroke="{CM}" stroke-width="2.6" clip-path="url(#cashclip)"/>')
    for c, color, dy in (("market", COL["market"], 0), ("founder", COL["founder"], 1)):
        s = series[c]; tm = cases[c]["capital_breakdown"]["trough_month"]; need = cases[c]["peak_capital_need"]
        if tm:
            x, y = ax.X(tm), ax.Y(s[tm - 1])
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#fff" stroke="{color}" stroke-width="2.5"/>')
            ly = y + 20 if c == "market" else y + 36   # both below their troughs on separate rows; the zero-crossing labels sit above (market) / just below (team) the zero line
            rt = x > W * 0.62
            body.append(f'<text x="{x + (-8 if rt else 8):.1f}" y="{ly:.1f}" text-anchor="{"end" if rt else "start"}" font-size="12" font-weight="700" fill="{color}">{E(L["need"])} {E(_money(need, cur))} · {_ml(tm)}</text>')
        zc = next((i + 1 for i in range(1, n) if s[i - 1] < 0 <= s[i]), None)
        if zc:
            body.append(f'<circle cx="{ax.X(zc):.1f}" cy="{y0:.1f}" r="4.5" fill="{color}"/>')
            right = ax.X(zc) > W * 0.62 or c == "founder"   # the team's label reads leftwards so it never runs into the market's
            ly = (y0 - 8) if c == "market" else (y0 + 18)   # market above the zero line, team below it
            body.append(f'<text x="{ax.X(zc) + (-6 if right else 6):.1f}" y="{ly:.1f}" text-anchor="{"end" if right else "start"}" font-size="12" fill="{color}">{E(L["payback_cash"])} {_ml(zc)}</text>')
    body.append(_legend([(L["market"], COL["market"], "line"), (L["team"], COL["founder"], "line"), (L["edges"], BAND, "rect")], ax.l, H - 6))
    return _svg(W, H, "".join(body), L["cash_title"], L["cash_sub"])


def capital_chart(case, cvr, cur, L, W=600, H=300):
    """Waterfall: outlays until the cash trough (stacked by kind) − gross profit earned by then = capital need; next to it,
    what is usual for the chosen funding path. capital_sentence() gives the prose that reads the chart out."""
    b = case["capital_breakdown"]; need = case["peak_capital_need"]
    parts = [(k, L[k], c) for k, c in (("payroll", "#3B4CCA"), ("marketing", "#7C8CF0"), ("fixed", "#A5B0F5"), ("upfront", "#C9D0F9")) if b.get(k, 0) > 0]
    gross = sum(b[k] for k, _, _ in parts); off = b["gross_profit_offset"]
    have_round = bool(cvr) and cvr.get("position") in ("below_round", "inside_round", "above_round")
    rhi = cvr["round_high"] if have_round else 0
    top = max(gross, need, rhi, 1) * 1.12
    yt = _ticks(0, top); top = yt[-1]
    ax = _Ax(W, H, 0, 4 if have_round else 3, 0, top, pad=(50, 16, 64, 60))
    body = [ax.grid(cur, yt, [])]
    bw = (ax.X(1) - ax.X(0)) * 0.56
    def bar(i, y0v, y1v, col, dash=False):
        x = ax.X(i + 0.5) - bw / 2
        st = f' stroke="{col}" stroke-width="1.5" stroke-dasharray="5 4" fill="{col}" fill-opacity="0.12"' if dash else f' fill="{col}"'
        return f'<rect x="{x:.1f}" y="{ax.Y(max(y0v, y1v)):.1f}" width="{bw:.1f}" height="{abs(ax.Y(y0v) - ax.Y(y1v)):.1f}" rx="3"{st}/>'
    def label(i, v, text, col=INK, dy=-6, bold=True):
        return f'<text x="{ax.X(i + 0.5):.1f}" y="{ax.Y(v) + dy:.1f}" text-anchor="middle" font-size="12.5" font-weight="{700 if bold else 400}" fill="{col}">{E(text)}</text>'
    def xlab(i, text):
        return "".join(f'<text x="{ax.X(i + 0.5):.1f}" y="{H - ax.b + 16 + j * 13}" text-anchor="middle" font-size="11.5" fill="{MUTED}">{E(ln)}</text>' for j, ln in enumerate(_wrap(text, 20)))
    y = 0
    for k, lab, c in parts:
        seg = bar(0, y, y + b[k], c)
        if abs(ax.Y(y) - ax.Y(y + b[k])) < 3: seg = seg.replace('height="', 'height="3" data-h="', 1)   # a sliver stays visible
        body.append(seg)
        if b[k] / top > 0.07: body.append(label(0, y + b[k] / 2, _money(b[k], cur), "#fff", dy=4, bold=False))
        y += b[k]
    body.append(label(0, gross, _money(gross, cur), dy=-10)); body.append(xlab(0, L["spent"]))
    body.append(bar(1, gross, gross - off, CM).replace(f'fill="{CM}"', f'fill="{CM}" fill-opacity="0.35"')); body.append(label(1, gross, "−" + _money(off, cur), CM, dy=-10)); body.append(xlab(1, L["covered"]))
    body.append(bar(2, 0, need, CM)); body.append(label(2, need, _money(need, cur), CM)); body.append(xlab(2, L["need_x"].format(m=b["trough_month"])))
    con = f'stroke="{MUTED}" stroke-width="1" stroke-dasharray="3 3"'
    body.append(f'<line x1="{ax.X(0.5) + bw/2:.1f}" x2="{ax.X(1.5) - bw/2:.1f}" y1="{ax.Y(gross):.1f}" y2="{ax.Y(gross):.1f}" {con}/>')
    body.append(f'<line x1="{ax.X(1.5) + bw/2:.1f}" x2="{ax.X(2.5) - bw/2:.1f}" y1="{ax.Y(need):.1f}" y2="{ax.Y(need):.1f}" {con}/>')
    if have_round:
        col = MUTED
        body.append(bar(3, cvr.get("round_low") or 0, rhi, col, dash=True)); body.append(label(3, rhi, L["upto_x"].format(x=_money(rhi, cur)), CP if need > rhi else CO, dy=-10))
        body.append(xlab(3, L["usual_for"].format(path=L["paths"].get(cvr["path"], cvr["path"]))))
    body.append(_legend([(lab, c, "rect") for _, lab, c in parts] + [(L["gp_short"], "#B0B7E8", "rect")], ax.l, H - 6, W))
    return _svg(W, H, "".join(body), L["cap_title"], L["cap_sub"])


def capital_sentence(case, cvr, cur, L, round_phrase):
    b = case["capital_breakdown"]; need = case["peak_capital_need"]
    parts = [(L[k], b[k]) for k in ("payroll", "marketing", "fixed", "upfront") if b.get(k, 0) > 0]
    gross = sum(v for _, v in parts)
    items = ", ".join(f"{lab.lower()} {_money(v, cur)}" for lab, v in parts)
    s = L["cap_sentence"].format(m=b["trough_month"], gross=_money(gross, cur), items=items, off=_money(b["gross_profit_offset"], cur), need=_money(need, cur))
    if round_phrase: s += " " + L["cap_round"].format(text=round_phrase)
    return s


def flags_html(ue, be, months, cvr, L, round_phrase=""):
    """Rule check: the model's market-case numbers against the usual early-stage thresholds — metric · rule · in the model · reading."""
    lc = ue.get("ltv_cac_headline", ue.get("ltv_cac")); pb = ue.get("payback_headline", ue.get("payback_months")); cur = cur_of(cvr)
    loaded = (ue.get("sales_share_of_payroll") or 0) > 0
    rows = []
    v = L["f_inf"] if lc is None else f"{lc:.1f}×"
    rows.append(("green" if (lc is None or lc >= 3) else ("amber" if lc >= 1 else "red"), L["f_ltvcac"] + (" " + L["f_loaded"] if loaded else ""), L["r_ltvcac"], v))
    v = L["f_never"] if pb is None else f"{pb} {L['f_mo']}"
    rows.append(("red" if pb is None else ("amber" if pb > 18 else "green"), L["f_payback"], L["r_payback"], v))
    v = L["f_no_be"].format(n=months) if be is None else _ml(be)
    rows.append(("red" if be is None else ("green" if be <= 12 else "amber"), L["f_be"], L["r_be"].format(n=months), v))
    if cvr and cvr.get("position") in ("below_round", "inside_round", "above_round"):
        rule = L["r_capital"].format(path=L["paths"].get(cvr["path"], cvr["path"]), rng=L["upto_x"].format(x=_money(cvr["round_high"], cur)))
        val = _money(cvr["capital_need"], cur) + (f" — {round_phrase}" if round_phrase else "")
        rows.append(("red" if cvr["position"] == "above_round" else "green", L["f_capital"], rule, val))
    out = [f'<p class="flags-intro">{E(L["flags_intro"])}</p><table class="t flags"><thead><tr><th>{E(L["c_metric"])}</th><th>{E(L["c_rule"])}</th><th>{E(L["c_model"])}</th><th>{E(L["c_verdict"])}</th></tr></thead><tbody>']
    for lvl, lab, rule, val in rows:
        out.append(f'<tr><td><b>{E(lab)}</b></td><td class="grey">{E(rule)}</td><td>{E(val)}</td><td><span class="lamp {lvl}"></span>{E(L["verdicts"][lvl])}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def cur_of(cvr):
    return {"EUR": "€", "USD": "$", "GBP": "£"}.get((cvr or {}).get("model_currency") or "", "")


def bridge_chart(rows, cur, L, T_dom, measured=False, W=980, H=None):
    """Horizontal bars: the effect of each assumption alone (capital need, or revenue in measured mode). rows = model bridge rows."""
    key = "revenue_end" if measured else "peak_capital_need"
    rows = [b for b in rows if (b.get(key) or {}).get("delta")][:8]
    if not rows: return ""
    rows = sorted(rows, key=lambda b: -abs(b[key]["delta"]))
    H = H or (70 + 34 * len(rows))
    fv = lambda b, v: (f"{v:g} %" if b["kind"] == "pct" else (_money(v, cur) if b["kind"] == "money" else f"{v:g}"))
    a_, b_ = ("measured", "category") if measured else ("market", "founder")
    labels = [(f"{b['line']} · " if b.get("line") else "") + (f"{T_dom.get(b['domain'], b['domain'])}: {fv(b, b[a_])} → {fv(b, b[b_])}" if b["kind"] != "joint" else T_dom.get("joint", "budget + customers")) for b in rows]
    deltas = [b[key]["delta"] for b in rows]
    mx = max(abs(x) for x in deltas) or 1
    l, r = 300, 110; zero = l + (W - l - r) * (abs(min(0, min(deltas))) / (mx + abs(min(0, min(deltas))))) if min(deltas) < 0 else l
    scale = (W - l - r) / (mx + (abs(min(deltas)) if min(deltas) < 0 else 0))
    good_up = measured
    body = [f'<line x1="{zero:.1f}" x2="{zero:.1f}" y1="44" y2="{H - 26}" stroke="{INK}" stroke-width="1"/>']
    for i, (lab, dl) in enumerate(zip(labels, deltas)):
        y = 50 + i * 34; w = abs(dl) * scale; col = CO if (dl > 0) == good_up else CP
        x = zero if dl >= 0 else zero - w
        body.append(f'<text x="{l - 10}" y="{y + 15}" text-anchor="end" font-size="12.5" fill="{INK}">{E(lab)}</text>')
        body.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="22" rx="3" fill="{col}" opacity="0.9"/>')
        lx = (zero + w + 8) if dl >= 0 else (zero - w - 8); anc = "start" if dl >= 0 else "end"; fill = col
        if dl >= 0 and lx > W - 70: lx, anc, fill = zero + w - 8, "end", "#fff"   # bar runs to the edge: label inside the bar
        if dl < 0 and lx < l + 10: lx, anc, fill = zero - w + 8, "start", "#fff"
        body.append(f'<text x="{lx:.1f}" y="{y + 15}" text-anchor="{anc}" font-size="12.5" font-weight="700" fill="{fill}">{"+" if dl > 0 else "−"}{E(_money(abs(dl), cur))}</text>')
    body.append(f'<text x="{W}" y="{H - 6}" text-anchor="end" font-size="11" fill="{MUTED}" font-style="italic">{E(L["note_bridge"])}</text>')
    return _svg(W, H, "".join(body), L["bridge_title_m"] if measured else L["bridge_title"])


def lines_chart(cases, key, title, cur, L, money=True, W=980, H=380, subtitle=None):
    """Four cases as lines (team and market solid, the edges dashed) for one projection field: mrr, cumulative, customers."""
    pm = cases["market"]["projection"]; n = len(pm); xs = [r["month"] for r in pm]
    series = {c: [r[key] for r in cases[c]["projection"]] for c in ("founder", "market", "pessimistic", "optimistic") if c in cases}
    same = series.get("founder") == series.get("market")
    if same: series.pop("founder", None)   # identical series would hide one another; the legend says so
    main = series["market"] + series.get("founder", []) + [0]
    allv = [v for s in series.values() for v in s] + [0]
    y_hi = min(max(allv), max(main) * 1.8 if max(main) > 0 else max(allv)); y_lo = max(min(allv), min(main) * 1.8 if min(main) < 0 else min(allv))
    yt = _ticks(y_lo * 1.05, y_hi * 1.06); ax = _Ax(W, H, 0.5, n + 0.5, yt[0], yt[-1])
    clip = f'<defs><clipPath id="lc{key}"><rect x="{ax.l}" y="{ax.t}" width="{W - ax.l - ax.r}" height="{H - ax.t - ax.b}"/></clipPath></defs>'
    xt = [m for m in xs if m % (6 if n > 18 else 3) == 0 or m == 1]
    body = [clip, ax.grid(cur, yt, xt, money=money)]
    y0 = ax.Y(0)
    if yt[0] < 0 < yt[-1]: body.append(f'<line x1="{ax.l}" x2="{W - ax.r}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{INK}" stroke-width="1"/>')
    style = {"pessimistic": (CP, 1.6, "5 4"), "optimistic": (CO, 1.6, "5 4"), "founder": (CF, 2.4, None), "market": (CM, 2.8, None)}
    for c in ("pessimistic", "optimistic", "founder", "market"):
        if c not in series: continue
        col, w, dash = style[c]
        da = f' stroke-dasharray="{dash}"' if dash else ""
        body.append(f'<path d="{ax.path(xs, series[c])}" fill="none" stroke="{col}" stroke-width="{w}"{da} clip-path="url(#lc{key})"/>')
    legend = [(L["market"] + (f" = {L['team'].lower()}" if same else ""), CM, "line")] + ([] if same else [(L["team"], CF, "line")]) + [(L["edge_lo"], CP, "dash"), (L["edge_hi"], CO, "dash")]
    body.append(_legend(legend, ax.l, H - 6, W))
    return _svg(W, H, "".join(body), title, subtitle)


def tornado_chart(rows, base_cap, cur, L, T_dom, W=980, H=None):
    """Tornado on the market ranges: for each assumption, capital need at its low and high edge (base = market case).
    Bars show how much the outcome depends on each assumption — including rows where the team gave no number."""
    rows = [r for r in rows if r["width_capital"] > 0][:8]
    if len(rows) < 2: return ""
    H = H or (88 + 30 * len(rows))
    vals = [base_cap] + [r["low"]["peak_capital_need"] for r in rows] + [r["high"]["peak_capital_need"] for r in rows]
    lo_v, hi_v = min(vals), max(vals); span = (hi_v - lo_v) or 1
    l, r_ = 400, 90; scale = (W - l - r_) / span
    X = lambda v: l + (v - lo_v) * scale
    fv = lambda r, v: (f"{v:g}\u202f%" if r["kind"] == "pct" else (_money(v, cur) if r["kind"] == "money" else f"{v:g}"))
    body = [f'<line x1="{X(base_cap):.1f}" x2="{X(base_cap):.1f}" y1="52" y2="{H - 28}" stroke="{INK}" stroke-width="1.2"/>',
            f'<text x="{X(base_cap):.1f}" y="48" text-anchor="middle" font-size="11" fill="{MUTED}">{E(L["t_base"])} {E(_money(base_cap, cur))}</text>']
    for i, r in enumerate(rows):
        y = 58 + i * 30
        lab = f"{T_dom.get(r['domain'], r['label'])}: {fv(r, r['low']['value'])} – {fv(r, r['high']['value'])}" + (f" · {L['t_noteam']}" if r.get("fill") == "filled_from_market" else "")
        body.append(f'<text x="{l - 10}" y="{y + 14}" text-anchor="end" font-size="12" fill="{INK}">{E(lab)}</text>')
        for edge in ("low", "high"):
            v = r[edge]["peak_capital_need"]
            x0, x1 = sorted((X(base_cap), X(v))); col = CO if v < base_cap else CP
            body.append(f'<rect x="{x0:.1f}" y="{y}" width="{max(1.5, x1 - x0):.1f}" height="20" rx="2" fill="{col}" opacity="0.85"><title>{E(edge)}: {E(_money(v, cur))}</title></rect>')
            if abs(x1 - x0) >= 2:
                lx = (x1 + 6) if v > base_cap else (x0 - 6); anc = "start" if v > base_cap else "end"
                if v > base_cap and lx > W - 60: lx, anc = x1 - 6, "end"
                if v < base_cap and lx < l + 4: lx, anc = x0 + 6, "start"
                body.append(f'<text x="{lx:.1f}" y="{y + 14}" text-anchor="{anc}" font-size="10.5" fill="{col if anc in ("start", "end") and not (v > base_cap and lx == x1 - 6) and not (v < base_cap and lx == x0 + 6) else "#fff"}">{E(_money(v, cur))}</text>')
    body.append(f'<text x="{W}" y="{H - 6}" text-anchor="end" font-size="11" fill="{MUTED}" font-style="italic">{E(L["t_note"])}</text>')
    return _svg(W, H, "".join(body), L["t_title"], L["t_sub"])
