#!/usr/bin/env python3
"""
Render the financial dashboard page from the model output (founder case vs market case).

    python build_dashboard.py model.json out_dir [--lang ru|en] [--currency €] [--line NAME]

Writes out_dir/dashboard.png — one landscape panel: KPI tiles (founder | market), monthly revenue and cumulative cash
for the four cases (founder and market solid, pessimistic/optimistic dashed), LTV vs CAC per case, break-even per case,
and the BRIDGE: starting from the market case, what happens to capital need if the founder is right about one
assumption — and out_dir/bridge.png (the bridge chart alone, for the report). Writes dashboard.json with the model
fingerprint and PNG hashes AFTER the images exist.

Single-line model → uses its cases. Multi-line → "combined" for revenue / cash / break-even and the first line (or --line)
for unit economics and the bridge; the subtitle says so. Every number on the page comes from model.json.
"""
import json
import os
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from financial_model import CASES  # noqa: E402

L = {
    "en": {"title": "Financial dashboard — team's numbers vs market numbers", "note_bridge": "bars do not add up: assumptions interact",
           "title_measured": "Financial dashboard — the business as measured vs the category", "measured_lbl": "Measured", "category_lbl": "Category",
           "bridge_measured": "If ONE metric reached the category level (rest as measured) — change in revenue at the last month", "sub_single": "{n}-month model · founder's numbers vs market numbers · dashed: benchmark range (pessimistic / optimistic)",
           "sub_multi": "{n}-month model, all revenue lines combined · unit economics and bridge for line “{line}”",
           "rev": "Monthly revenue", "cash": "Cumulative cash", "capneed": "capital need", "ue": "Lifetime value vs. cost to acquire",
           "ltv": "Lifetime value", "cac": "Cost to acquire", "be": "Break-even", "none": "not within {n} mo", "month": "Month",
           "bridge": "If the founder is right about ONE assumption (market case otherwise) — change in capital need",
           "k_ltvcac": "LTV / CAC — founder | market", "k_payback": "Payback, months — founder | market", "k_be": "Break-even — founder | market",
           "k_cap": "Capital need — founder | market", "k_rev": "Revenue, month {n} — founder | market", "k_arpu3": "Revenue per customer needed for 3× (market)",
           "mo": "mo", "founder": "Founder", "market": "Market", "pessimistic": "Joint worst case", "optimistic": "Joint best case", "case": "Case", "nopay": "never"},
    "ru": {"title": "Финансовая картина — команда и рынок", "note_bridge": "столбики не складываются: допущения взаимодействуют",
           "title_measured": "Финансовый дашборд — бизнес как измерен против категории", "measured_lbl": "Измерено", "category_lbl": "Категория",
           "bridge_measured": "Если ОДНА метрика выйдет на уровень категории (остальное — как измерено) — изменение выручки в последний месяц", "sub_single": "Модель на {n} месяцев · оценки команды и рыночные оценки · пунктир: диапазон бенчмарков (пессимистичный / оптимистичный)",
           "sub_multi": "Модель на {n} месяцев, все линии выручки вместе · юнит-экономика и мост — по линии «{line}»",
           "rev": "Выручка в месяц", "cash": "Накопленный денежный поток", "capneed": "потребность в капитале",
           "ue": "Пожизненная ценность клиента против стоимости привлечения", "ltv": "Ценность клиента (LTV)", "cac": "Стоимость привлечения (CAC)",
           "be": "Выход в плюс", "none": "нет за {n} мес", "month": "Месяц",
           "bridge": "Если основатель прав в ОДНОМ допущении (остальное — рынок) — как меняется потребность в капитале",
           "k_ltvcac": "LTV / CAC — команда | рынок", "k_payback": "Окупаемость, мес — команда | рынок", "k_be": "Выход в плюс — команда | рынок",
           "k_cap": "Потребность в капитале — команда | рынок", "k_rev": "Выручка, месяц {n} — команда | рынок", "k_arpu3": "Нужная выручка с клиента для 3× (рынок)",
           "mo": "мес", "founder": "Команда", "market": "Рынок", "pessimistic": "Пессимистичный", "optimistic": "Оптимистичный", "case": "Кейс", "nopay": "никогда"},
}
DOM = {
    "en": {"pricing": "price", "project_value": "project value", "projects_per_year": "projects / client / yr", "gmv_per_customer_month": "GMV per customer",
           "take_rate": "take rate", "gross_margin": "gross margin", "monthly_churn": "monthly churn", "expansion": "expansion", "repeat_rate": "repeat rate",
           "cac": "cost to acquire", "monthly_budget": "acquisition budget", "new_customers_per_month": "new customers / mo", "fte_cost": "cost per FTE", "joint": "budget + customers together"},
    "ru": {"pricing": "цена", "project_value": "стоимость проекта", "projects_per_year": "проектов на клиента в год", "gmv_per_customer_month": "оборот на клиента",
           "take_rate": "комиссия", "gross_margin": "валовая маржа", "monthly_churn": "отток в месяц", "expansion": "рост чека", "repeat_rate": "доля повторов",
           "cac": "стоимость привлечения", "monthly_budget": "бюджет привлечения", "new_customers_per_month": "новых клиентов в мес", "fte_cost": "стоимость FTE", "joint": "бюджет + клиенты вместе"},
}
from chart_style import COL, apply as _apply_style, INK as _INK, MUTED as _MUTED
STY = {"founder": "-", "market": "-", "pessimistic": "--", "optimistic": "--"}
NAVY = _INK; GREY = _MUTED; LIGHT = "#F5F6FA"


def esc(s):
    """matplotlib treats a pair of $ as math mode; escape every $ in drawn text."""
    return str(s).replace("$", r"\$")


def money(x, cur):
    from chart_style import fmt_money
    return fmt_money(x, cur)


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    model = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    for stale in ("dashboard.json",):
        try: os.remove(os.path.join(out, stale))
        except FileNotFoundError: pass
    lang = (sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "en").lower()
    cur = sys.argv[sys.argv.index("--currency") + 1] if "--currency" in sys.argv else "$"
    multi = "lines" in model
    n = model["months"]
    T = {k: (v.replace("{n}", str(n)) if isinstance(v, str) else v) for k, v in L.get(lang, L["en"]).items()}; D = DOM.get(lang, DOM["en"])
    measured = model.get("mode") == "measured"
    if measured:   # a live business: tiles and bridge read "measured | category" and "if one metric reached the category level"
        f_old, m_old = T["founder"], T["market"]
        for k in list(T):
            if k.startswith(("k_", "sub_")) and isinstance(T[k], str):
                T[k] = T[k].replace(f_old.lower(), T["measured_lbl"].lower()).replace(m_old.lower(), T["category_lbl"].lower()).replace("оценки команды и рыночные оценки", "измеренные цифры против категории").replace("founder's numbers vs market numbers", "measured numbers vs the category").replace("основателя", "измеренные").replace("founder's", "measured")
        T.update({"founder": T["measured_lbl"], "market": T["category_lbl"], "bridge": T["bridge_measured"], "title": T["title_measured"]})
    if multi:
        line = sys.argv[sys.argv.index("--line") + 1] if "--line" in sys.argv else next(iter(model["lines"]))
        if line not in model["lines"]: raise SystemExit(f"--line {line!r} not in model; have {list(model['lines'])}")
        ln = model["lines"][line]; ue = ln["cases"]
        src = model["combined"]["bridge_to_market"] if measured else model["combined"]["bridge"]
        br = [dict(b, label=f"{b['line']} · {b['label']}") for b in src]
        proj = {c: model["combined"][c]["projection"] for c in CASES}
        be = {c: model["combined"][c]["breakeven_month"] for c in CASES}; cap = {c: model["combined"][c]["peak_capital_need"] for c in CASES}
        subtitle = T["sub_multi"].replace("{line}", line)
    else:
        ue = model["cases"]; br = model["bridge_to_market"] if measured else model["bridge"]
        proj = {c: ue[c]["projection"] for c in CASES}; be = {c: ue[c]["breakeven_month"] for c in CASES}; cap = {c: ue[c]["peak_capital_need"] for c in CASES}
        subtitle = T["sub_single"]
    F, M = ue["founder"], ue["market"]
    fm = lambda f: f"{f(F)} | {f(M)}"

    _apply_style(plt)
    fig = plt.figure(figsize=(13.5, 9.4), dpi=160); fig.patch.set_facecolor("white")
    gs = GridSpec(4, 6, figure=fig, height_ratios=[0.9, 2.2, 2.2, 2.1], hspace=0.62, wspace=0.55, left=0.05, right=0.98, top=0.90, bottom=0.06)
    fig.text(0.05, 0.955, esc(T["title"]), fontsize=17, weight="bold", color=NAVY, ha="left")
    fig.text(0.05, 0.925, esc(subtitle), fontsize=9, color=GREY, ha="left")

    tiles = [
        (T["k_ltvcac"], fm(lambda c: f"{c['unit_economics']['ltv_cac']:.1f}×" if c["unit_economics"]["ltv_cac"] is not None else "∞")),
        (T["k_payback"], fm(lambda c: str(c["unit_economics"]["payback_months"]) if c["unit_economics"]["payback_months"] else T["nopay"])),
        (T["k_be"], f"{'M' + str(be['founder']) if be['founder'] else '—'} | {'M' + str(be['market']) if be['market'] else '—'}"),
        (T["k_cap"], f"{money(cap['founder'], cur)} | {money(cap['market'], cur)}"),
        (T["k_rev"], f"{money(proj['founder'][-1]['mrr'], cur)} | {money(proj['market'][-1]['mrr'], cur)}"),
        (T["k_arpu3"], money(M["unit_economics"].get("arpu_for_ltv_cac_3"), cur)),
    ]
    for i, (lab, val) in enumerate(tiles):
        ax = fig.add_subplot(gs[0, i]); ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, color=LIGHT, zorder=0))
        ax.text(0.5, 0.64, esc(val), ha="center", va="center", fontsize=13 if len(val) < 14 else 10.5, weight="bold", color=NAVY, transform=ax.transAxes)
        ax.text(0.5, 0.2, esc("\n".join(textwrap.wrap(lab, 26)[:2])), ha="center", va="center", fontsize=6.8, color=GREY, transform=ax.transAxes, linespacing=1.1)

    fmt = mticker.FuncFormatter(lambda x, _: esc(money(x, cur)))
    def style(ax, title):
        ax.set_title(title, fontsize=10.5, loc="left", color=NAVY, weight="bold", pad=8)
        ax.grid(alpha=0.25); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.tick_params(labelsize=8); ax.set_xlabel(T["month"], fontsize=8, color=GREY)

    for key, slot, title in (("mrr", gs[1, 0:3], T["rev"]), ("cumulative", gs[1, 3:6], T["cash"])):
        ax = fig.add_subplot(slot)
        for c in ("pessimistic", "optimistic", "market", "founder"):
            ax.plot([r["month"] for r in proj[c]], [r[key] for r in proj[c]], color=COL[c], lw=2.2 if c in ("founder", "market") else 1.2, ls=STY[c], label=T[c])
        if key == "cumulative":
            ax.axhline(0, color="#999", lw=0.8)
            ys = [r["cumulative"] for r in proj["market"]]; i_min = ys.index(min(ys))
            if min(ys) < 0:
                ax.annotate(esc(f"{T['capneed']} ({T['market'].lower()}): {money(cap['market'], cur)}"), xy=(i_min + 1, min(ys)), xycoords="data",
                            xytext=(0.03, 0.06), textcoords="axes fraction", ha="left", va="bottom", fontsize=8, color=NAVY,
                            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=NAVY, lw=0.6), arrowprops=dict(arrowstyle="->", color=NAVY, lw=0.8, shrinkB=3))
        ax.yaxis.set_major_formatter(fmt); style(ax, title); ax.legend(frameon=False, fontsize=7.5, ncol=2)

    ax = fig.add_subplot(gs[2, 0:3]); x = range(4)
    ltv = [ue[c]["unit_economics"]["ltv"] for c in CASES]; cac = [ue[c]["inputs"]["blended_cac"] for c in CASES]
    ax.bar([i - 0.18 for i in x], ltv, 0.36, color=[COL[c] for c in CASES], alpha=0.85, label=T["ltv"])
    ax.bar([i + 0.18 for i in x], cac, 0.36, color="#B0B7C3", label=T["cac"])
    for i, c in enumerate(CASES):
        r = ue[c]["unit_economics"]["ltv_cac"]
        ax.text(i, max(ltv[i], cac[i]) * 1.04, f"{r:.1f}×" if r is not None else "∞", ha="center", fontsize=8.5, weight="bold", color=COL[c])
    ax.set_xticks(list(x)); ax.set_xticklabels([T[c] for c in CASES], fontsize=7.5)
    ax.yaxis.set_major_formatter(fmt); style(ax, T["ue"]); ax.set_xlabel(T["case"], fontsize=8, color=GREY); ax.legend(frameon=False, fontsize=7.5)

    ax = fig.add_subplot(gs[2, 3:6])
    for i, c in enumerate(CASES):
        v = be[c]
        ax.barh(i, v if v else n, color=COL[c] if v else "#E6E8EC", height=0.5)
        ax.text((v if v else n) + 0.5, i, f"M{v}" if v else T["none"], va="center", fontsize=8, color=COL[c] if v else GREY)
    ax.set_yticks(list(range(4))); ax.set_yticklabels([T[c] for c in CASES], fontsize=7.5); ax.set_xlim(0, n * 1.35); ax.invert_yaxis()
    style(ax, T["be"]); ax.grid(axis="y", alpha=0)

    # ── bridge
    ax = fig.add_subplot(gs[3, :]); pos = ax.get_position(); ax.set_position([0.24, pos.y0, 0.98 - 0.24, pos.height])
    key = "revenue_end" if measured else "peak_capital_need"
    rows = [b for b in br if (b.get(key) or {}).get("delta") is not None][:8]
    labels, deltas = [], []
    if rows:
        rows = sorted(rows, key=lambda b: abs(b[key]["delta"]))
        fv = lambda b, v: (f"{v:g} %" if b["kind"] == "pct" else (money(v, cur) if b["kind"] == "money" else f"{v:g}"))
        a_, b_ = ("measured", "category") if measured else ("market", "founder")
        labels = [(f"{b['line']} · " if b.get("line") else "") + (f"{D.get(b['domain'], b['domain'])}: {fv(b, b[a_])} → {fv(b, b[b_])}" if b["kind"] != "joint" else D.get("joint", "budget + customers together")) for b in rows]
        deltas = [b[key]["delta"] for b in rows]
        good_up = measured   # revenue delta: up is good; capital delta: down is good
        labels = [esc(l) for l in labels]
        ax.barh(labels, deltas, color=[(COL["optimistic"] if (d > 0) == good_up else COL["pessimistic"]) for d in deltas], height=0.55)
        mx = max(map(abs, deltas)) or 1
        for i, d in enumerate(deltas):
            ax.text(d + (mx * 0.01 if d >= 0 else -mx * 0.01), i, esc(("+" if d > 0 else "") + money(d, cur)), va="center", ha="left" if d >= 0 else "right", fontsize=8, color=GREY)
        ax.axvline(0, color="#999", lw=0.8); ax.xaxis.set_major_formatter(fmt); ax.tick_params(labelsize=8)
        ax.set_title(esc(T["bridge"]), fontsize=9.5 if len(T["bridge"]) > 90 else 10.5, loc="left", color=NAVY, weight="bold", pad=8, wrap=True)
        ax.text(1.0, -0.22, T["note_bridge"], transform=ax.transAxes, ha="right", fontsize=7.5, color=GREY, style="italic")
        ax.grid(axis="x", alpha=0.25); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.set_xlim(-mx * 1.35 if min(deltas) < 0 else -mx * 0.05, mx * 1.35 if max(deltas) > 0 else mx * 0.05)
    else:
        ax.axis("off"); ax.text(0.5, 0.5, "—", ha="center")
    fig.savefig(os.path.join(out, "dashboard.png"), facecolor="white"); plt.close(fig)

    files = ["dashboard.png"]
    if rows:
        fig, ax = plt.subplots(figsize=(9.5, max(2.3, 1.1 + 0.42 * len(rows))), dpi=160)
        ax.barh(labels, deltas, color=[(COL["optimistic"] if (d > 0) == good_up else COL["pessimistic"]) for d in deltas], height=0.5)
        for i, d_ in enumerate(deltas):
            ax.text(d_ + (mx * 0.01 if d_ >= 0 else -mx * 0.01), i, esc(("+" if d_ > 0 else "") + money(d_, cur)), va="center", ha="left" if d_ >= 0 else "right", fontsize=8, color=GREY)
        ax.set_xlim(-mx * 1.35 if min(deltas) < 0 else -mx * 0.05, mx * 1.35 if max(deltas) > 0 else mx * 0.05)
        ax.axvline(0, color="#999", lw=0.8); ax.xaxis.set_major_formatter(fmt); ax.tick_params(labelsize=8)
        ax.set_title(esc("\n".join(textwrap.wrap(T["bridge"], 80)[:2])), fontsize=9.5, loc="left", color=NAVY, weight="bold", pad=8)
        ax.grid(axis="x", alpha=0.6); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        fig.subplots_adjust(left=0.36, right=0.97, top=0.78 if len(rows) > 2 else 0.68, bottom=0.2 if len(rows) < 3 else 0.12); fig.savefig(os.path.join(out, "bridge.png"), facecolor="white"); plt.close(fig)
        files.append("bridge.png")
    from build_workbook import write_manifest
    write_manifest(out, "dashboard.json", model, files, {"line": line if multi else None, "lang": lang, "currency": cur, "mode": model.get("mode")})
    print(json.dumps({"dashboard": os.path.join(out, "dashboard.png"), "bridge": os.path.join(out, "bridge.png") if rows else None}))


if __name__ == "__main__":
    main()
