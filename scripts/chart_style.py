"""Shared look for every matplotlib chart the skill produces (dashboard, bridge, workbook charts).

Palette matches the PDF renderer: team orange, market indigo, red / green edges, ink text, soft grid.
Registers the bundled Roboto (assets/fonts) so charts and the PDF share one typeface; falls back to DejaVu.
"""
import os

TEAM, MARKET, PESS, OPT = "#F28C28", "#3B4CCA", "#DC2626", "#16A34A"
INK, MUTED, GRID, LIGHT = "#1B1F3B", "#6B7280", "#E5E7EB", "#F5F6FA"
COL = {"founder": TEAM, "market": MARKET, "pessimistic": PESS, "optimistic": OPT}
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")


def apply(plt):
    from matplotlib import font_manager
    fam = "DejaVu Sans"
    if os.path.isdir(FONT_DIR):
        for f in os.listdir(FONT_DIR):
            if f.lower().endswith(".ttf"):
                try: font_manager.fontManager.addfont(os.path.join(FONT_DIR, f))
                except Exception: pass
        if any("Roboto" in f.name for f in font_manager.fontManager.ttflist): fam = "Roboto"
    plt.rcParams.update({"font.family": [fam, "DejaVu Sans"] if fam != "DejaVu Sans" else fam, "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.edgecolor": GRID, "axes.titlecolor": INK, "axes.titleweight": "bold", "grid.color": GRID, "grid.alpha": 1.0,
                         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "figure.facecolor": "white"})
    return fam


MFMT = "M{v}"      # month label format ("M9" / "9-й мес."), set by build_report.build()
DEC = "."          # decimal separator for the current build (build_report sets "," for ru)
THIN = "\u202f"    # narrow no-break space as thousands separator


def fmt_money(x, cur):
    """One money format for prose, tables, tiles and charts: €1 500 below 10 000 · €88k from 10 000 · €1.2M from 1 000 000.
    Axis ticks in charts may pass round values and get the same result."""
    if x is None: return "—"
    a = abs(x); s = "−" if x < 0 else ""
    if a >= 1e6: return f"{s}{cur}{a/1e6:.1f}M".replace(".", DEC)
    if a >= 1e4: return f"{s}{cur}{a/1e3:.0f}k"
    if a >= 1e3: return f"{s}{cur}{a:,.0f}".replace(",", THIN)
    return f"{s}{cur}{a:.0f}"


def fmt_pct(v, digits=1):
    if v is None: return "—"
    s = f"{v:.{digits}f}"
    if s.endswith("0") and "." in s: s = s.rstrip("0").rstrip(".")
    return s.replace(".", DEC) + "\u202f%"


def fmt_mult(v):
    if v is None: return None
    return (f"{v:.0f}×" if v >= 10 else f"{v:.1f}×".replace(".", DEC))
