"""Gráficos estáticos (matplotlib) para o relatório PDF."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .events import LEVEL_COLOR  # noqa: E402
from .i18n import phase as _ph, t as _t  # noqa: E402
from .phases import PHASE_PT  # noqa: E402

INK, MUTED, GRID = "#0A0A0B", "#6B7280", "#E5E7EB"
PHASE_COLOR = {
    "GROUND": "#F3F4F6", "TAXI_OUT": "#F3F4F6", "TAXI_IN": "#EDEEF0", "TAKEOFF": "#DBEAFE", "INITIAL_CLIMB": "#E0F2FE", "CLIMB": "#ECFEFF",
    "CRUISE": "#F0FDF4", "DESCENT": "#FEFCE8", "APPROACH": "#FFF7ED", "LANDING": "#FEE2E2",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6,
})


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _shade_phases(ax, phase, t_scale=60.0):
    vals = phase.values
    t = phase.index.values / t_scale
    start = 0
    for i in range(1, len(vals) + 1):
        if i == len(vals) or vals[i] != vals[start]:
            ax.axvspan(t[start], t[min(i, len(t) - 1)], color=PHASE_COLOR.get(vals[start], "#fff"), lw=0, zorder=0)
            start = i


def _col(fa, key, *fallbacks):
    m = fa.mapping or {}
    for c in [m.get(key), *fallbacks]:
        if c and c in fa.df:
            return c
    return None


def _tmin(fa, t):
    return (np.asarray(t, dtype=float) - fa.df.index[0]) / 60.0


def flight_profile(fa, lang: str = "pt") -> bytes:
    df = fa.df
    alt_c = _col(fa, "altitude", "ALT_STD")
    spd_c = _col(fa, "airspeed", "IAS") or _col(fa, "groundspeed", "GS")
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    ph = fa.phase.copy()
    ph.index = _tmin(fa, ph.index)
    _shade_phases(ax, ph, t_scale=1.0)
    tm = _tmin(fa, df.index.values)
    ax.plot(tm, df[alt_c], color=INK, lw=1.4)
    ax.set_ylabel(_t("ax_alt", lang))
    ax.set_xlabel(_t("ax_tmin", lang))
    if spd_c:
        ax2 = ax.twinx()
        ax2.plot(tm, df[spd_c], color="#8E9299", lw=0.9, alpha=0.85)
        ax2.set_ylabel(f"{spd_c} (kt)", color="#6E737B")
        ax2.grid(False)
        ax2.spines["right"].set_visible(True)
    top = ax.get_ylim()[1]
    for e in fa.events:
        x = _tmin(fa, e.peak_t)
        ax.axvline(x, color=LEVEL_COLOR[e.level], lw=1.1, ls="--")
        ax.text(x, top * 0.98, str(e.level), color="white", fontsize=7, ha="center", va="top",
                bbox=dict(boxstyle="circle,pad=0.2", fc=LEVEL_COLOR[e.level], ec="none"))
    present = list(dict.fromkeys(fa.phase.values))
    handles = [plt.Rectangle((0, 0), 1, 1, fc=PHASE_COLOR.get(p, "#fff"), ec=GRID) for p in present]
    ax.legend(handles, [_ph(p, lang) for p in present], loc="upper center", bbox_to_anchor=(0.5, -0.22),
              ncol=min(5, len(present)), frameon=False, fontsize=7)
    return _png(fig)


def route_map(fa, lang: str = "pt") -> bytes | None:
    """Rota sobre a linha de costa (Natural Earth), colorida por altitude, com aeroportos e eventos."""
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Polygon

    from . import geo
    la, lo = _col(fa, "latitude"), _col(fa, "longitude")
    alt_c = _col(fa, "altitude", "ALT_STD")
    if not la or not lo:
        return None
    d = fa.df[[la, lo, alt_c]].dropna()
    d = d[(d[la].abs() <= 90) & (d[lo].abs() <= 180)]
    if len(d) < 10:
        return None
    lat, lon, alt = d[la].values, d[lo].values, d[alt_c].values
    pad_y = max(2.0, (lat.max() - lat.min()) * 0.12)
    pad_x = max(2.0, (lon.max() - lon.min()) * 0.12)
    x0, x1, y0, y1 = lon.min() - pad_x, lon.max() + pad_x, lat.min() - pad_y, lat.max() + pad_y
    k = np.cos(np.radians((y0 + y1) / 2))
    want = 1.55  # largura/altura do mapa
    if (x1 - x0) * k / (y1 - y0) < want:
        cx, half = (x0 + x1) / 2, want * (y1 - y0) / k / 2
        x0, x1 = cx - half, cx + half
    else:
        cy, half = (y0 + y1) / 2, (x1 - x0) * k / want / 2
        y0, y1 = cy - half, cy + half
    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    ax.set_facecolor("#F4F6F8")
    for poly in geo.land_polygons():
        xs = [p[0] for p in poly]
        if max(xs) < x0 - 5 or min(xs) > x1 + 5:
            continue
        ax.add_patch(Polygon(poly, closed=True, fc="#E2E4E8", ec="#B4B8BF", lw=0.4, zorder=1))
    pts = np.column_stack([lon, lat])
    segs = np.stack([pts[:-1], pts[1:]], axis=1)
    lc = LineCollection(segs, cmap="viridis", lw=2.0, zorder=3)
    lc.set_array(alt[:-1])
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label(_t("ax_altft", lang), fontsize=7)
    cb.ax.tick_params(labelsize=6.5)
    for key, i in (("origin", 0), ("destination", -1)):
        ap = geo.nearest_airport(lat[i], lon[i])
        ax.plot(lon[i], lat[i], marker="s", ms=6, color=INK, zorder=5)
        ax.annotate(ap["icao"] if ap else key, (lon[i], lat[i]), xytext=(5, 5), textcoords="offset points",
                    fontsize=8, fontweight="bold", color=INK, zorder=6)
    t = fa.df.index.values
    for n, e in enumerate(fa.events, start=1):
        j = int(np.clip(np.searchsorted(t, e.peak_t), 0, len(t) - 1))
        ey, ex = fa.df[la].iloc[j], fa.df[lo].iloc[j]
        if ey != ey:
            continue
        ax.plot(ex, ey, "o", ms=9, color=LEVEL_COLOR[e.level], mec="white", mew=1, zorder=7)
        ax.annotate(str(n), (ex, ey), ha="center", va="center", fontsize=6, color="white", zorder=8,
                    fontweight="bold")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
    ax.set_xlabel(_t("ax_lon", lang))
    ax.set_ylabel(_t("ax_lat", lang))
    ax.grid(color="white", lw=0.5)
    return _png(fig)


def approach_map(fa, which: str = "destination", minutes: float = 8.0, lang: str = "pt") -> bytes | None:
    """Vista de pormenor da descolagem ou da aproximação final, com eventos."""
    la, lo = _col(fa, "latitude"), _col(fa, "longitude")
    if not la or not lo or "liftoff_s" not in fa.marks:
        return None
    t = fa.df.index.values
    if which == "destination":
        tc = fa.marks["touchdown_s"]
        sel = (t >= tc - minutes * 60) & (t <= tc + 90)
    else:
        tc = fa.marks["liftoff_s"]
        sel = (t >= tc - 90) & (t <= tc + minutes * 60)
    d = fa.df[sel].dropna(subset=[la, lo])
    alt_c = _col(fa, "altitude")
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    sc = ax.scatter(d[lo], d[la], c=d[alt_c], s=4, cmap="viridis", zorder=3)
    from . import geo
    ap = geo.nearest_airport(float(d[la].iloc[-1 if which == "destination" else 0]),
                             float(d[lo].iloc[-1 if which == "destination" else 0]))
    if ap:
        ax.plot(ap["lon"], ap["lat"], "s", color=INK, ms=6, zorder=4)
        ax.annotate(ap["icao"], (ap["lon"], ap["lat"]), xytext=(4, 4), textcoords="offset points", fontsize=8,
                    fontweight="bold")
    for n, e in enumerate(fa.events, start=1):
        if sel[int(np.clip(np.searchsorted(t, e.peak_t), 0, len(t) - 1))]:
            j = int(np.clip(np.searchsorted(t, e.peak_t), 0, len(t) - 1))
            ax.plot(fa.df[lo].iloc[j], fa.df[la].iloc[j], "o", ms=9, color=LEVEL_COLOR[e.level], mec="white", zorder=6)
            ax.annotate(str(n), (fa.df[lo].iloc[j], fa.df[la].iloc[j]), ha="center", va="center", fontsize=6,
                        color="white", zorder=7, fontweight="bold")
    mid = float(d[la].mean())
    kx = np.cos(np.radians(mid))
    cy, cx = (d[la].max() + d[la].min()) / 2, (d[lo].max() + d[lo].min()) / 2
    half = max(d[la].max() - d[la].min(), (d[lo].max() - d[lo].min()) * kx) / 2 * 1.15 + 0.01
    ax.set_ylim(cy - half, cy + half)
    ax.set_xlim(cx - half / kx, cx + half / kx)
    ax.set_aspect(1 / kx)
    ax.set_title(_t("app_map" if which == "destination" else "dep_map", lang), fontsize=8)
    ax.tick_params(labelsize=6)
    cb = fig.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label(f"{alt_c} (ft)", fontsize=6)
    cb.ax.tick_params(labelsize=6)
    return _png(fig)


def parameter_overview(fa, params: list[str], lang: str = "pt") -> bytes:
    """Painel com os parâmetros principais ao longo do voo, eventos marcados."""
    ps = [p for p in params if p in fa.df]
    fig, axs = plt.subplots(len(ps), 1, figsize=(7.2, 1.15 * len(ps) + 0.4), sharex=True)
    axs = np.atleast_1d(axs)
    tm = _tmin(fa, fa.df.index.values)
    for ax, p in zip(axs, ps):
        s = fa.native.get(p) if fa.native else None
        if s is not None and len(s) > len(fa.df) * 1.5:
            ax.plot(_tmin(fa, s.index.values), s.values, color=INK, lw=0.5)
        else:
            ax.plot(tm, fa.df[p], color=INK, lw=0.8)
        ax.set_ylabel(p, fontsize=6.5, rotation=0, ha="right", va="center")
        ax.tick_params(labelsize=6)
        for e in fa.events:
            ax.axvline(_tmin(fa, e.peak_t), color=LEVEL_COLOR[e.level], lw=0.8, ls="--")
    axs[-1].set_xlabel(_t("ax_tmin", lang))
    fig.subplots_adjust(hspace=0.15)
    return _png(fig)


def parameter_chart(fa, ed, events, lang: str = "pt") -> bytes:
    """Série do disparador à volta do evento, com bandas de risco por nível e condição de deteção."""
    from .events import _defined, _op
    s = (fa.native or {}).get(ed.parameter)
    if s is None:
        s = fa.df[ed.parameter]
    t0 = min(e.start_s for e in events) - 60
    t1 = max(e.end_s for e in events) + 60
    base = fa.df.index[0]
    w = s[(s.index >= t0) & (s.index <= t1)]
    w = pd.Series(w.values, index=w.index - base)
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    ph = fa.phase[(fa.phase.index >= t0) & (fa.phase.index <= t1)]
    if len(ph):
        ph = pd.Series(ph.values, index=ph.index - base)
        _shade_phases(ax, ph, t_scale=1.0)
    y = w.abs() if ed.mode == "abs_max" else w
    ax.plot(w.index, y, color=INK, lw=1.2)
    op = _op(ed)
    lv = _defined(ed)
    lo, hi = ax.get_ylim()
    ths = [th for _, th, _ in lv]
    span = max(1e-6, max(hi, *ths) - min(lo, *ths))
    for i, (lvl, th, dur) in enumerate(lv):
        nxt = lv[i + 1][1] if i + 1 < len(lv) else (th + 0.15 * span if op == ">" else th - 0.15 * span)
        ax.axhspan(th, nxt, color=LEVEL_COLOR[lvl], alpha=0.13, lw=0)
        ax.axhline(th, color=LEVEL_COLOR[lvl], lw=0.8, ls=":")
        ax.text(w.index.min() if len(w) else 0, th, f" N{lvl} {th:g}" + (f" · {dur:g}s" if dur else ""),
                fontsize=6.5, color=LEVEL_COLOR[lvl], va="bottom")
    for e in events:
        pv = abs(e.peak) if ed.mode == "abs_max" else e.peak
        ax.axvspan(e.start_s - base, e.end_s - base + 0.5, color=LEVEL_COLOR[e.level], alpha=0.08, lw=0)
        ax.plot(e.peak_t - base, pv, "o", color=LEVEL_COLOR[e.level], ms=6, zorder=5)
        ax.annotate(f"{e.peak:.2f} {ed.units}", (e.peak_t - base, pv), textcoords="offset points", xytext=(6, 6),
                    fontsize=7.5, color=LEVEL_COLOR[e.level], fontweight="bold")
    ax.set_ylabel(f"{ed.parameter} ({ed.units})" if ed.units else ed.parameter, fontsize=7)
    ax.set_xlabel(_t("ax_ts", lang))
    return _png(fig)


def risk_bar(counts: dict) -> bytes:
    fig, ax = plt.subplots(figsize=(3.2, 1.6))
    lv = [1, 2, 3]
    vals = [counts[k] for k in lv]
    ax.barh(["Nível 1", "Nível 2", "Nível 3"], vals, color=[LEVEL_COLOR[k] for k in lv], height=0.6)
    for i, v in enumerate(vals):
        ax.text(v + 0.05, i, str(v), va="center", fontsize=8, color=INK)
    ax.set_xlim(0, max(vals + [1]) * 1.3)
    ax.grid(axis="y", visible=False)
    ax.invert_yaxis()
    return _png(fig)

