"""Relatório PDF profissional de análise FDM (reportlab)."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from . import charts
from .events import LEVEL_COLOR
from .i18n import level as _lv, mitigation as _mit, phase as _ph, t as _t

_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("Sans", str(_FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Bold", str(_FONT_DIR / "DejaVuSans-Bold.ttf")))

INK = colors.HexColor("#0A0A0B")
SILVER = colors.HexColor("#B4B8BF")
LOGO = Path(__file__).resolve().parents[1] / "assets" / "vektor_mark.png"
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E5E7EB")
ACCENT = colors.HexColor("#6E737B")

S = {
    "h1": ParagraphStyle("h1", fontName="Sans-Bold", fontSize=20, leading=24, textColor=INK),
    "h2": ParagraphStyle("h2", fontName="Sans-Bold", fontSize=13, leading=17, textColor=INK, spaceBefore=6, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName="Sans-Bold", fontSize=10.5, leading=14, textColor=INK, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Sans", fontSize=9, leading=13, textColor=INK, alignment=TA_LEFT),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=7.5, leading=10, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=8, leading=10.5, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Sans-Bold", fontSize=8, leading=10.5, textColor=INK),
    "kpi": ParagraphStyle("kpi", fontName="Sans-Bold", fontSize=16, leading=19, textColor=INK),
    "kpil": ParagraphStyle("kpil", fontName="Sans", fontSize=7.5, leading=9, textColor=MUTED),
}


def _fmt(v, nd=2):
    try:
        return f"{v:.{nd}f}"
    except (TypeError, ValueError):
        return "-"


def _th(v):
    return "-" if v is None or v != v else f"{v:g}"


def _derived_inputs(fa, ed) -> list[str]:
    from .expr import refs
    der = set(getattr(fa.decoded.layout, "derived", {}) or {}) | {"Height Above Airfield"}
    names = {ed.parameter} | {n for n, _ in refs(ed.parameter)} | {n for n, _ in refs(ed.detection or "")}
    return sorted(n for n in names if n in der)


def _hms(s):
    s = int(s)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _img(png: bytes, width_mm: float) -> Image:
    im = Image(io.BytesIO(png))
    ratio = im.imageHeight / im.imageWidth
    w = min(width_mm, 225.0 / ratio)  # nunca mais alto do que a área útil da página
    im.drawWidth = w * mm
    im.drawHeight = w * mm * ratio
    return im


def _badge(level: int, lang: str) -> Paragraph:
    c = LEVEL_COLOR[level]
    return Paragraph(f'<font color="{c}"><b>●</b></font> {_lv(level, lang)}', S["cell"])


def _table(rows, widths, header=True, zebra=True):
    t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
               ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK)]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFAFB")))
    t.setStyle(TableStyle(st))
    return t


def _on_page(company: str, lang: str):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(INK)
        canvas.rect(0, h - 11 * mm, w, 11 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(SILVER)
        canvas.setLineWidth(0.6)
        canvas.line(0, h - 11 * mm, w, h - 11 * mm)
        if LOGO.exists():
            canvas.drawImage(str(LOGO), 13 * mm, h - 10.2 * mm, 9.4 * mm, 9.4 * mm, mask="auto")
        canvas.setFont("Sans-Bold", 9)
        canvas.setFillColor(colors.white)
        canvas.drawString(25 * mm, h - 6.4 * mm, "V E K T O R")
        canvas.setFont("Sans", 7.5)
        canvas.setFillColor(SILVER)
        canvas.drawString(48 * mm, h - 6.4 * mm, f"{company}  ·  {_t('rep_band', lang)}")
        canvas.drawRightString(w - 15 * mm, h - 6.4 * mm, _t("rep_conf", lang))
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 10 * mm, _t("rep_footer", lang))
        canvas.drawRightString(w - 15 * mm, 10 * mm, f"vektor.aero  ·  {_t('page', lang)} {doc.page}")
        canvas.restoreState()
    return draw


def build_pdf(fa, company: str = "Vektor FDM", lang: str = "pt") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm,
                            title=_t("rep_title", lang), author=company)
    m, r = fa.meta, fa.risk
    story = []

    # --- Cabeçalho ---
    leg = f"{m.get('origin', '-')} → {m.get('destination', '-')}"
    names = " · ".join(x for x in (m.get("origin_name"), m.get("destination_name")) if x)
    seg = _t("seg_of", lang, i=m["flight_index"], n=m["flights_in_download"]) if m.get("flights_in_download") else ""
    story += [Paragraph(_t("rep_title", lang), S["h1"]), Spacer(1, 2 * mm),
              Paragraph(f"<b>{m.get('registration', '-')}</b> · {m['aircraft_type']} · <b>{leg}</b>"
                        + (f" · {_t('flight', lang)} {m['flight_no']}" if m.get("flight_no") else "")
                        + (f" · {m['flight_date']}" if m.get("flight_date") else ""), S["p"]),
              Paragraph(names, S["small"]),
              Paragraph(_t("generated", lang, d=f"{datetime.now():%Y-%m-%d %H:%M}", p=m["profile"])
                        + (f" · {seg}" if seg else ""), S["small"]),
              Spacer(1, 4 * mm)]
    if not m.get("layout_validated", True):
        warn = Table([[Paragraph(_t("warn_layout", lang), S["cell"])]], colWidths=[180 * mm])
        warn.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
                                  ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E07A1F")),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [warn, Spacer(1, 4 * mm)]

    lvl = r["max_level"]
    lvl_txt = _lv(lvl, lang)
    kpis = [
        [Paragraph(f'<font color="{LEVEL_COLOR[lvl]}">{lvl_txt.split(" · ")[0]}</font>', S["kpi"]),
         Paragraph(str(len(fa.events)), S["kpi"]),
         Paragraph(str(r["risk_index"]), S["kpi"]),
         Paragraph(f"{m.get('block_air_min', 0):.0f} min", S["kpi"]),
         Paragraph(f"{m['quality_pct']:.1f}%", S["kpi"])],
        [Paragraph(_t("kpi_max", lang) + (f" ({lvl_txt.split(' · ')[1].lower()})" if lvl else ""), S["kpil"]),
         Paragraph(_t("kpi_events", lang), S["kpil"]), Paragraph(_t("kpi_index", lang), S["kpil"]),
         Paragraph(_t("kpi_air", lang), S["kpil"]), Paragraph(_t("kpi_sync", lang), S["kpil"])],
    ]
    kt = Table(kpis, colWidths=[44 * mm, 30 * mm, 42 * mm, 32 * mm, 32 * mm])
    kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
                            ("LINEAFTER", (0, 0), (-2, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story += [kt, Spacer(1, 6 * mm)]

    c = r["counts"]
    n_av = int(fa.stats["available"].sum()) if len(fa.stats) else 0
    base = dict(np=m["n_params"], dur=_hms(m["duration_s"]), nav=n_av, nt=len(fa.stats))
    if fa.events:
        top = fa.events[0]
        resumo = _t("sum_events", lang, **base, ne=len(fa.events), c3=c[3], c2=c[2], c1=c[1], top=top.name,
                    phase=_ph(top.phase, lang).lower(), peak=_fmt(top.peak), u=top.units, lvl=top.level,
                    th=_th(top.thresholds[top.level - 1]))
    else:
        resumo = _t("sum_none", lang, **base)
    story += [Paragraph(_t("s1", lang), S["h2"]), Paragraph(resumo, S["p"]), Spacer(1, 4 * mm),
              _img(charts.flight_profile(fa, lang), 180), Paragraph(_t("cap_profile", lang), S["small"])]
    rm = charts.route_map(fa, lang)
    if rm:
        story += [PageBreak(), Paragraph(_t("route", lang), S["h2"]), _img(rm, 180),
                  Paragraph(_t("cap_route", lang), S["small"]), Spacer(1, 3 * mm)]
        dm, am = charts.approach_map(fa, "origin", lang=lang), charts.approach_map(fa, "destination", lang=lang)
        if dm and am:
            story.append(Table([[_img(dm, 86), _img(am, 86)]], colWidths=[90 * mm, 90 * mm]))
    ov = [p for p in ("Pressure Altitude", "Radio Height", "Groundspeed", "Computed Airspeed", "Vertical Speed",
                      "Pitch Angle", "Roll Angle", "Vertical Acceleration", "ALT_STD", "IAS", "RALT", "PITCH",
                      "ROLL", "VRTG") if p in fa.df]
    if len(ov) >= 3:
        story += [PageBreak(), Paragraph(_t("overview", lang), S["h2"]), _img(charts.parameter_overview(fa, ov, lang), 180)]

    # --- 2. Parâmetros monitorizados ---
    story += [PageBreak(), Paragraph(_t("s2", lang), S["h2"]), Paragraph(_t("s2_intro", lang), S["p"]), Spacer(1, 3 * mm)]
    rows = [[Paragraph(h, S["cellb"]) for h in [_t("th_event", lang), _t("th_peak", lang), "N1", "N2", "N3",
                                                 _t("th_class", lang), _t("th_n", lang)]]]
    for _, st in fa.stats.iterrows():
        name = Paragraph(f"{st['name']}<br/><font color='#6B7280'>{st['parameter']}</font>", S["cell"])
        if not st["available"]:
            miss = st.get("missing") if isinstance(st.get("missing"), list) else []
            rows.append([name, Paragraph(_t("not_eval", lang, x=", ".join(miss[:3]) or "-"), S["small"]),
                         "", "", "", "", ""])
            continue
        pk = st["peak"]
        pk_txt = _t("out_phase", lang) if pk != pk else f"{_fmt(pk)} {st['units'] or ''}"
        rows.append([name, Paragraph(pk_txt, S["cell"]),
                     Paragraph(_th(st["L1"]), S["cell"]), Paragraph(_th(st["L2"]), S["cell"]),
                     Paragraph(_th(st["L3"]), S["cell"]), _badge(int(st["level"]), lang),
                     Paragraph(str(int(st["n_events"])), S["cell"])])
    story.append(_table(rows, [56, 28, 15, 15, 15, 41, 10]))

    # --- 3. Eventos ---
    story += [PageBreak(), Paragraph(_t("s3", lang), S["h2"])]
    if not fa.events:
        story.append(Paragraph(_t("no_events", lang), S["p"]))
    defs = {d.id: d for d in fa.defs}
    t0 = fa.df.index[0]
    for n, e in enumerate(fa.events, start=1):
        ed = defs[e.id]
        der = _derived_inputs(fa, ed)
        head = Paragraph(f'{n}. {ed.name} <font color="{LEVEL_COLOR[e.level]}">· {_lv(e.level, lang)}</font>', S["h3"])
        lims = " / ".join(_th(x) for x in ed.thresholds)
        sub = _t("ev_sub", lang, c=ed.code or ed.id, p=ed.parameter, op=ed.op or "", lims=lims, u=ed.units,
                 ph=", ".join(_ph(p, lang) for p in ed.phases) or _t("all", lang))
        if ed.detection:
            sub += f" · {_t('cond', lang)}: {ed.detection}"
        block = [head, Paragraph(sub, S["small"]), Spacer(1, 1.5 * mm),
                 _img(charts.parameter_chart(fa, ed, [e], lang), 178),
                 Paragraph(_t("ev_text", lang, a=_hms(e.start_s - t0), b=_hms(e.end_s - t0), ph=_ph(e.phase, lang),
                              pk=_fmt(e.peak), u=e.units), S["p"])]
        if der:
            block.append(Paragraph(_t("derived_note", lang, x=", ".join(der)), S["small"]))
        block.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(block))

    # --- 4. Mitigação ---
    story += [PageBreak(), Paragraph(_t("s4", lang), S["h2"])]
    if not fa.events:
        story.append(Paragraph(_t("no_events_trend", lang), S["p"]))
    else:
        rows = [[Paragraph(h, S["cellb"]) for h in [_t("th_event", lang).split(" /")[0], _t("th_level", lang),
                                                     _t("th_actions", lang), _t("th_owner", lang), _t("th_due", lang)]]]
        for n, e in enumerate(fa.events, start=1):
            acts = "<br/>".join(f"• {_mit(a, lang)}" for a in e.mitigation) or _t("trend_only", lang)
            rows.append([Paragraph(f"{n}. {e.name}<br/><font color='#6B7280'>{_fmt(e.peak)} {e.units}</font>", S["cell"]),
                         _badge(e.level, lang), Paragraph(acts, S["cell"]),
                         Paragraph(_t(f"own{e.level}", lang), S["cell"]), Paragraph(_t(f"due{e.level}", lang), S["cell"])])
        story.append(_table(rows, [40, 25, 70, 27, 18]))
    story += [Spacer(1, 8 * mm), Paragraph(_t("method", lang), S["h3"]), Paragraph(_t("method_txt", lang), S["small"])]

    # --- Anexo A ---
    lay = fa.decoded.layout
    story += [PageBreak(), Paragraph(_t("annex", lang), S["h2"]),
              Paragraph(_t("annex_txt", lang, dur=_hms(m.get("download_duration_s", m["duration_s"])),
                           wps=lay.words_per_second, fmt=lay.storage, q=f"{m['quality_pct']:.1f}", sl=m["sync_losses"])
                        + (" " + lay.notes if lay.notes else ""), S["p"]), Spacer(1, 3 * mm)]
    rows = [[Paragraph(h, S["cellb"]) for h in [_t("th_param", lang), _t("th_loc", lang), _t("th_enc", lang),
                                                 _t("th_scale", lang), _t("th_evid", lang)]]]
    for name, pd_ in lay.params.items():
        sfs = sorted({sf for sf, _ in pd_.locations})
        wds = sorted({w for _, w in pd_.locations})
        loc = (_t("all_sf", lang) if sfs == [1, 2, 3, 4] else ",".join(map(str, sfs))) + " / " + ",".join(map(str, wds))
        rows.append([Paragraph(f"{name}<br/><font color='#6B7280'>{pd_.units}</font>", S["cell"]),
                     Paragraph(loc + (f" {_t('fine', lang)}" if pd_.fine_offset else ""), S["cell"]),
                     Paragraph(pd_.encoding.upper(), S["cell"]), Paragraph(f"{pd_.scale:g}", S["cell"]),
                     Paragraph(pd_.description, S["small"])])
    story.append(_table(rows, [34, 30, 18, 18, 80]))
    if getattr(lay, "derived", None):
        story += [Spacer(1, 3 * mm), Paragraph(_t("derived_title", lang), S["h3"]),
                  Paragraph("; ".join(f"{k} = {v}" for k, v in lay.derived.items()) + "; " + _t("haa_note", lang), S["small"])]

    doc.build(story, onFirstPage=_on_page(company, lang), onLaterPages=_on_page(company, lang))
    return buf.getvalue()
