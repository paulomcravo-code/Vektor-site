"""
Vektor FDM · portal online de Flight Data Monitoring.

Cliente: envia o download da aeronave -> análise automática -> acompanha o estado -> descarrega o
relatório depois de aprovado pela Vektor e com a subscrição ativa.
Dono (Vektor): vê e guarda tudo, revê e aprova cada relatório, gere clientes, aeronaves e subscrições.

Executar localmente:  streamlit run app.py
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fdm import notify, storage
from fdm import workflow as wf
from fdm.events import LEVEL_COLOR
from fdm.i18n import LANGS
from fdm.i18n import level as _lv
from fdm.i18n import phase as _ph
from fdm.i18n import t as _t
from fdm.pipeline import analyse_download, list_profiles
from fdm.report import build_pdf

BRAND = os.environ.get("FDM_BRAND", "Vektor FDM")
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "vektor_mark.png")
OWNER_USER = os.environ.get("OWNER_USER", "owner")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD") or os.environ.get("APP_PASSWORD")
MODULE_KEYS = ["FDM", "SMS", "QUALITY", "PART-IS", "SAF", "RAMP", "LIBRARY", "MANPOWER"]

st.set_page_config(page_title=BRAND, page_icon=LOGO_PATH, layout="wide")
st.markdown("""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Michroma&family=Exo+2:wght@400;500;600&family=Chakra+Petch:wght@500;600&display=swap">
<style>
html, body, [class*="css"] {font-family:"Exo 2",system-ui,sans-serif;}
h1, h2, h3 {font-family:"Michroma","Eurostile",sans-serif !important; font-weight:400 !important; letter-spacing:.03em;}
.block-container {padding-top: 1.6rem; max-width: 1280px;}
.kpi {border:1px solid #2E3035; border-radius:10px; padding:14px 16px; background:#141416;}
.kpi .v {font-size:1.6rem; font-weight:600; color:#EDEEF0; line-height:1.1; font-family:"Chakra Petch",sans-serif}
.kpi .l {font-size:.78rem; color:#9B9EA4; margin-top:4px}
.vk-lock b {font-family:"Michroma",sans-serif; font-weight:400; letter-spacing:.26em; font-size:1.1rem; color:#EDEEF0}
.vk-lock span {display:block; font:600 .62rem "Chakra Petch",sans-serif; letter-spacing:.3em; color:#C4C7CD; text-transform:uppercase}
.pill {display:inline-block; padding:2px 10px; border-radius:999px; color:#fff; font-size:.78rem; font-weight:600}
.st-tag {display:inline-block; padding:2px 10px; border-radius:6px; border:1px solid #3A3D44; font-size:.78rem; color:#DCDEE2}
</style>""", unsafe_allow_html=True)

wf.import_env_clients()


# ---------------------------------------------------------------- idioma
def L() -> str:
    return st.session_state.get("lang", "pt")


def tr(key: str, **kw) -> str:
    return _t(key, L(), **kw)


def lang_picker(where, key: str):
    cur = L()
    sel = where.selectbox("🌐 " + tr("lang"), list(LANGS), index=list(LANGS).index(cur),
                          format_func=lambda k: LANGS[k], key=key)
    if sel != cur:
        st.session_state.lang = sel
        if st.session_state.get("role") == "client":
            wf.upsert_client(st.session_state.client, lang=sel)
        st.rerun()


# ---------------------------------------------------------------- acesso
SECRET = os.environ.get("SECRET_KEY") or (OWNER_PASSWORD or "local") + "-vektor"


def _sign(role: str, cid: str | None, hours: int = 12) -> str:
    import hashlib
    import hmac
    import time
    exp = int(time.time()) + hours * 3600
    body = f"{role}|{cid or ''}|{exp}"
    sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}|{sig}"


def _restore() -> bool:
    """Mantém a sessão depois de recarregar a página (token assinado no endereço, válido 12 h)."""
    import hashlib
    import hmac
    import time
    tok = st.query_params.get("s")
    if not tok or tok.count("|") != 3:
        return False
    role, cid, exp, sig = tok.split("|")
    good = hmac.new(SECRET.encode(), f"{role}|{cid}|{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, good) or int(exp) < time.time():
        return False
    if role == "client":
        cl = wf.client(cid)
        if not cl or not cl.get("active"):
            return False
        st.session_state.setdefault("lang", cl.get("lang") or "pt")
    st.session_state.role, st.session_state.client = role, (cid or None)
    return True


def _enter(role: str, cid: str | None):
    st.session_state.role, st.session_state.client = role, cid
    st.query_params["s"] = _sign(role, cid)
    st.rerun()


def gate() -> bool:
    if not OWNER_PASSWORD and not wf.clients():
        st.session_state.role, st.session_state.client = "owner", None  # modo local sem login
        return True
    if st.session_state.get("role") or _restore():
        return True
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.image(LOGO_PATH, width=80)
        st.markdown('<div class="vk-lock"><b>VEKTOR</b><span>FDM portal</span></div>', unsafe_allow_html=True)
        lang_picker(st, "lang_login")
        with st.form("login"):
            uid = st.text_input(tr("login_user"))
            pw = st.text_input(tr("login_pw"), type="password")
            if st.form_submit_button(tr("login_btn"), type="primary"):
                owner_ids = {OWNER_USER.lower(), (os.environ.get("OWNER_EMAIL") or "").lower()} - {""}
                if uid.strip().lower() in owner_ids and OWNER_PASSWORD and secrets.compare_digest(pw, OWNER_PASSWORD):
                    wf.audit("owner", "login")
                    _enter("owner", None)
                cl = wf.find_login(uid.strip())
                if cl and wf.check_pw(pw, cl.get("pw_hash")):
                    if "FDM" not in wf.modules(cl):
                        st.error(tr("no_fdm"))
                        st.stop()
                    st.session_state.lang = cl.get("lang") or L()
                    wf.audit(cl["id"], "login")
                    _enter("client", cl["id"])
                st.error(tr("login_bad"))
    return False


if not gate():
    st.stop()
ROLE = st.session_state.role
CID = st.session_state.client


# ---------------------------------------------------------------- componentes
def kpi(col, value, label, color="#EDEEF0"):
    col.markdown(f'<div class="kpi"><div class="v" style="color:{color}">{value}</div>'
                 f'<div class="l">{label}</div></div>', unsafe_allow_html=True)


def pill(level: int) -> str:
    return f'<span class="pill" style="background:{LEVEL_COLOR[level]}">{_lv(level, L())}</span>'


def status_tag(s: str) -> str:
    return f'<span class="st-tag">{tr("st_" + s)}</span>'


def _dark(fig, h):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="#141416",
                      paper_bgcolor="#0A0A0B", font_color="#C4C7CD")
    fig.update_xaxes(gridcolor="#2E3035")
    fig.update_yaxes(gridcolor="#2E3035")
    return fig


def _mcol(fa, key, *fb):
    for c in [(fa.mapping or {}).get(key), *fb]:
        if c and c in fa.df:
            return c
    return None


def profile_figure(fa):
    df = fa.df
    alt = _mcol(fa, "altitude", "ALT_STD")
    spd = _mcol(fa, "airspeed", "IAS") or _mcol(fa, "groundspeed", "GS")
    tm = (df.index - df.index[0]) / 60
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tm, y=df[alt], name=_t("ax_alt", L()), line=dict(color="#DCDEE2", width=2)))
    if spd:
        fig.add_trace(go.Scatter(x=tm, y=df[spd], name=f"{spd} (kt)", yaxis="y2", line=dict(color="#8E9299", width=1.2)))
    for n, e in enumerate(fa.events, start=1):
        fig.add_vline(x=(e.peak_t - df.index[0]) / 60, line=dict(color=LEVEL_COLOR[e.level], dash="dash", width=1.2),
                      annotation_text=str(n), annotation_font_color=LEVEL_COLOR[e.level])
    fig.update_layout(xaxis_title=_t("ax_tmin", L()), yaxis=dict(title=_t("ax_alt", L())),
                      yaxis2=dict(title="kt", overlaying="y", side="right"), legend=dict(orientation="h", y=1.1))
    return _dark(fig, 340)


def map_figure(fa):
    la, lo, alt = _mcol(fa, "latitude"), _mcol(fa, "longitude"), _mcol(fa, "altitude", "ALT_STD")
    if not la or not lo:
        return None
    d = fa.df[[la, lo, alt]].dropna().iloc[::5]
    fig = go.Figure(go.Scattergeo(lat=d[la], lon=d[lo], mode="markers",
                                  marker=dict(size=3, color=d[alt], colorscale="Viridis", colorbar=dict(title="ft")),
                                  hovertext=[f"{a:.0f} ft" for a in d[alt]], name="route"))
    t = fa.df.index.values
    for n, e in enumerate(fa.events, start=1):
        j = int(np.clip(np.searchsorted(t, e.peak_t), 0, len(t) - 1))
        fig.add_trace(go.Scattergeo(lat=[fa.df[la].iloc[j]], lon=[fa.df[lo].iloc[j]], mode="markers+text",
                                    text=[str(n)], textposition="top center",
                                    marker=dict(size=13, color=LEVEL_COLOR[e.level], line=dict(color="white", width=1)),
                                    hovertext=f"{e.name} · {_lv(e.level, L())} · {e.peak:.2f} {e.units}", name=e.name))
    fig.update_geos(fitbounds="locations", showcountries=True, countrycolor="#2E3035", landcolor="#1B1C1F",
                    oceancolor="#0E0F11", showocean=True, coastlinecolor="#5A5E66", bgcolor="#0A0A0B")
    fig.update_layout(showlegend=False)
    return _dark(fig, 460)


def param_figure(fa, ed, evs):
    s = (fa.native or {}).get(ed.parameter)
    if s is None:
        s = fa.df[ed.parameter]
    b = fa.df.index[0]
    y = s.abs() if ed.mode == "abs_max" else s
    fig = go.Figure(go.Scattergl(x=s.index - b, y=y, mode="lines", line=dict(color="#DCDEE2", width=1.3)))
    for i, th in enumerate(ed.thresholds, start=1):
        if th is not None:
            fig.add_hline(y=th, line=dict(color=LEVEL_COLOR[i], dash="dot", width=1),
                          annotation_text=f"N{i} {th:g}", annotation_font_color=LEVEL_COLOR[i])
    for e in evs:
        pv = abs(e.peak) if ed.mode == "abs_max" else e.peak
        fig.add_vrect(x0=e.start_s - b, x1=max(e.end_s, e.start_s + 1) - b, fillcolor=LEVEL_COLOR[e.level],
                      opacity=0.12, line_width=0)
        fig.add_trace(go.Scatter(x=[e.peak_t - b], y=[pv], mode="markers", marker=dict(color=LEVEL_COLOR[e.level], size=10)))
    if evs:
        fig.update_xaxes(range=[min(e.start_s for e in evs) - b - 90, max(e.end_s for e in evs) - b + 90])
    fig.update_layout(showlegend=False, xaxis_title=_t("ax_ts", L()), yaxis_title=f"{ed.parameter} ({ed.units})")
    return _dark(fig, 300)


def show_flight(fa, owner: bool):
    r, m = fa.risk, fa.meta
    if owner and not m.get("layout_validated", True):
        st.warning("Mapeamento de parâmetros provisório (engenharia inversa, não validado contra o LFL).")
    k = st.columns(5)
    kpi(k[0], _lv(r["max_level"], L()), _t("kpi_max", L()), LEVEL_COLOR[r["max_level"]])
    kpi(k[1], len(fa.events), _t("kpi_events", L()))
    kpi(k[2], r["risk_index"], _t("kpi_index", L()))
    kpi(k[3], f"{m.get('block_air_min', 0):.0f} min", _t("kpi_air", L()))
    kpi(k[4], f"{m['quality_pct']:.1f}%", _t("kpi_sync", L()))
    st.plotly_chart(profile_figure(fa), use_container_width=True)
    mf = map_figure(fa)
    if mf is not None:
        st.plotly_chart(mf, use_container_width=True)
    tabs = st.tabs([_t("s3", L()), _t("s2", L())] + (["Dados / Data"] if owner else []))
    with tabs[0]:
        if not fa.events:
            st.success(_t("no_events", L()))
        defs = {d.id: d for d in fa.defs}
        for n, e in enumerate(fa.events, start=1):
            with st.expander(f"{n}. {_lv(e.level, L())} · {e.name} · {e.peak:.2f} {e.units}", expanded=n <= 3):
                st.markdown(pill(e.level) + f" &nbsp; {_ph(e.phase, L())}", unsafe_allow_html=True)
                st.plotly_chart(param_figure(fa, defs[e.id], [e]), use_container_width=True, key=f"pf_{id(fa)}_{n}")
                from fdm.i18n import mitigation as _mit
                for a in e.mitigation or [_t("trend_only", L())]:
                    st.markdown(f"- {_mit(a, L())}")
    with tabs[1]:
        show = fa.stats[fa.stats["available"]].copy()
        if len(show):
            show["class"] = show["level"].map(lambda x: _lv(int(x), L()))
            st.dataframe(show[["name", "parameter", "peak", "units", "L1", "L2", "L3", "class", "n_events"]],
                         use_container_width=True, hide_index=True)
    if owner:
        with tabs[2]:
            miss = fa.stats[~fa.stats["available"]]
            if len(miss):
                st.markdown(f"**{len(miss)} eventos não avaliados por falta de parâmetros**")
                st.dataframe(miss.assign(falta=miss["missing"].map(lambda x: ", ".join(x) if isinstance(x, list) else ""))
                             [["name", "parameter", "falta"]], use_container_width=True, hide_index=True)
            st.download_button("CSV 1 Hz", fa.df.to_csv().encode("utf-8"), f"voo_{m['flight_index']}.csv",
                               key=f"csv_{id(fa)}")


def pdf_button(sid: int, idx: int, lang: str, label: str, key: str):
    """Botão de download; o PDF é gerado na primeira vez e guardado no servidor."""
    cached = wf.REPORTS / f"{sid}_{idx}_{lang}.pdf"
    s = wf.submission(sid)
    name = f"Vektor_FDM_{s['registration']}_{sid}_{idx}_{lang}.pdf"
    if cached.exists():
        if st.download_button("⬇️ " + label, cached.read_bytes(), name, "application/pdf", key=key, type="primary"):
            wf.audit(st.session_state.get("client") or "owner", "download", name)
    elif st.button("📄 " + label, key=key + "_gen"):
        with st.spinner("PDF..."):
            wf.report_pdf(sid, idx, lang, BRAND)
        st.rerun()


def sub_ok(cl: dict) -> bool:
    return wf.subscription_ok(cl, notify.stripe_active)


def notify_released_for(cid: str) -> int:
    return wf.release_notifications(cid)


# ---------------------------------------------------------------- barra lateral
st.sidebar.image(LOGO_PATH, width=64)
st.sidebar.markdown('<div class="vk-lock"><b>VEKTOR</b><span>FDM · vektor.aero</span></div>', unsafe_allow_html=True)
lang_picker(st.sidebar, "lang_side")
if ROLE == "client":
    me = wf.client(CID) or {"name": CID}
    st.sidebar.markdown(f"**{me['name']}**")
if st.sidebar.button(tr("signout")):
    for k in ("role", "client", "adhoc"):
        st.session_state.pop(k, None)
    st.query_params.clear()
    st.rerun()
if OWNER_PASSWORD or wf.clients():
    st.query_params["s"] = _sign(ROLE, CID)  # mantém a sessão ao mudar de página ou recarregar


# ================================================================ CLIENTE
def client_upload():
    st.title(tr("p_upload"))
    fleet = wf.aircraft(CID)
    if not fleet:
        st.info(tr("no_aircraft"))
        return
    with st.form("up", clear_on_submit=True):
        ac = st.selectbox(tr("aircraft"), fleet, format_func=lambda a: a["registration"])
        up = st.file_uploader(tr("file"))
        notes = st.text_area(tr("notes"), height=80)
        go_btn = st.form_submit_button(tr("send"), type="primary")
    if go_btn and up is not None:
        sid = wf.create_submission(CID, ac["registration"], ac["profile"], up.name, up.getvalue(), notes)
        with st.spinner(tr("processing")):
            fl = wf.process(sid)
        s = wf.submission(sid)
        notify.owner_new_upload(s, me["name"])
        wf.audit(CID, "upload", f"submission {sid} {up.name}")
        if s["status"] == "error":
            st.warning(tr("sent_err"))
        else:
            st.success(tr("sent_ok", n=len(fl)))


def sub_box(cl: dict):
    ok = sub_ok(cl)
    if ok:
        st.success(tr("sub_active") + (f" · {tr('until', d=cl['sub_until'])}" if cl.get("sub_until") else ""))
        return
    st.warning(tr("sub_inactive"))
    link = notify.payment_link(cl) if cl.get("billing") in ("stripe", "both") else None
    if link:
        st.link_button(tr("pay_now"), link, type="primary")
    if cl.get("billing") in ("manual", "both", None):
        st.caption(tr("pay_manual"))


def client_reports():
    st.title(tr("p_reports"))
    cl = wf.client(CID)
    sub_box(cl)
    ok = sub_ok(cl)
    if ok:
        notify_released_for(CID)
    subs = wf.submissions(CID)
    if not subs:
        st.info(tr("nothing_yet"))
        return
    rlang = st.selectbox(tr("report_lang"), list(LANGS), index=list(LANGS).index(L()), format_func=lambda k: LANGS[k])
    for s in subs:
        head = f"#{s['id']} · {s['registration']} · {s['filename']} · {s['uploaded_at'][:16]} · {tr('st_' + s['status'])}"
        with st.expander(head, expanded=s["status"] == "approved" and ok):
            if s["status"] in ("processing", "pending_review", "error"):
                st.markdown(status_tag("pending_review" if s["status"] == "error" else s["status"]), unsafe_allow_html=True)
                continue
            if s["status"] == "rejected":
                st.markdown(status_tag("rejected"), unsafe_allow_html=True)
                if s.get("review_note"):
                    st.info(f"{tr('returned_note')}: {s['review_note']}")
                continue
            if not ok:
                st.info(tr("locked_pay"))
                continue
            if s.get("review_note"):
                st.caption(f"{tr('returned_note')}: {s['review_note']}")
            for f in json.loads(s["summary"] or "[]"):
                c1, c2 = st.columns([3, 2])
                c1.markdown(f"**{tr('flight')} {f['i']}** · {f['origin']} → {f['destination']} · "
                            f"{(f['air_min'] or 0):.0f} min · " + pill(f["max_level"]) + f" · {f['n_events']} ev.",
                            unsafe_allow_html=True)
                with c2:
                    pdf_button(s["id"], f["i"], rlang, tr("download_pdf"), key=f"c_{s['id']}_{f['i']}_{rlang}")
            if st.toggle("📈 " + tr("view_flight"), key=f"view_{s['id']}"):
                fl = wf.flights(s["id"])
                if fl:
                    i = st.selectbox(tr("flights"), range(len(fl)), key=f"sel_{s['id']}",
                                     format_func=lambda k: f"{fl[k].meta['origin']} → {fl[k].meta['destination']}")
                    show_flight(fl[i], owner=False)


def trends(client_id: str):
    fl, ev = storage.flights(client_id), storage.events(client_id)
    if fl.empty:
        st.info(tr("nothing_yet"))
        return
    k = st.columns(4)
    kpi(k[0], len(fl), tr("n_flights"))
    kpi(k[1], len(ev), tr("n_events"))
    kpi(k[2], f"{100 * len(ev[ev.level == 3]) / max(len(fl), 1):.1f}", tr("l3_rate"), LEVEL_COLOR[3])
    kpi(k[3], fl["registration"].nunique(), tr("fleet"))
    if not ev.empty:
        c1, c2 = st.columns(2)
        piv = ev.groupby(["name", "level"]).size().unstack(fill_value=0)
        fig = go.Figure([go.Bar(y=piv.index, x=piv[lv], orientation="h", name=_lv(lv, L()),
                                marker_color=LEVEL_COLOR[lv]) for lv in sorted(piv.columns)])
        fig.update_layout(barmode="stack", title=tr("ev_by_type"))
        c1.plotly_chart(_dark(fig, 380), use_container_width=True)
        fig2 = go.Figure(go.Scatter(x=list(range(1, len(fl) + 1)), y=fl["risk_index"], mode="lines+markers",
                                    line=dict(color="#DCDEE2")))
        fig2.update_layout(title=tr("risk_trend"))
        c2.plotly_chart(_dark(fig2, 380), use_container_width=True)
    st.dataframe(fl.drop(columns=["client"]), use_container_width=True, hide_index=True)


def client_account():
    st.title(tr("p_account"))
    cl = wf.client(CID)
    st.markdown(f"**{cl['name']}** · {cl.get('email') or ''}")
    st.markdown("Módulos / Modules: " + ", ".join(wf.modules(cl)))
    sub_box(cl)
    st.markdown("### " + tr("aircraft"))
    st.dataframe(pd.DataFrame(wf.aircraft(CID))[["registration"]] if wf.aircraft(CID) else pd.DataFrame(),
                 hide_index=True)
    with st.form("pw"):
        st.markdown("### " + tr("login_pw"))
        a = st.text_input("New / Nova", type="password")
        b = st.text_input("Confirm / Confirmar", type="password")
        if st.form_submit_button("OK") and a and a == b and len(a) >= 10:
            wf.upsert_client(CID, pw_hash=wf.hash_pw(a))
            wf.audit(CID, "password_change")
            st.success("OK")


# ================================================================ DONO
def submission_detail(sid: int):
    s = wf.submission(sid)
    cl = wf.client(s["client_id"]) or {"name": s["client_id"]}
    st.markdown(f"### #{sid} · {cl['name']} · {s['registration']} · {s['filename']}  " + status_tag(s["status"]),
                unsafe_allow_html=True)
    st.caption(f"{s['uploaded_at']} · {s['size_bytes'] / 1e6:.1f} MB · perfil {s['profile']} · "
               f"subscrição {'ativa' if sub_ok(cl) else 'inativa'}" + (f" · notas: {s['notes']}" if s.get("notes") else ""))
    if s["status"] == "error":
        st.error(s.get("error") or "Erro")
    c1, c2 = st.columns([2, 1])
    profs = list_profiles()
    prof = c1.selectbox("Perfil de análise", profs, index=profs.index(s["profile"]) if s["profile"] in profs else 0,
                        key=f"prof_{sid}")
    if c2.button("🔁 Reprocessar", key=f"rp_{sid}"):
        wf.update_submission(sid, profile=prof, status="processing")
        with st.spinner("A reprocessar..."):
            wf.process(sid)
        st.rerun()
    fl = wf.flights(sid)
    if fl:
        i = st.selectbox("Voo", range(len(fl)), key=f"fsel_{sid}",
                         format_func=lambda k: f"{k + 1}: {fl[k].meta['origin']} → {fl[k].meta['destination']} · "
                                               f"{fl[k].meta.get('block_air_min', 0):.0f} min · {_lv(fl[k].risk['max_level'], 'pt')}")
        show_flight(fl[i], owner=True)
        st.markdown("#### Pré-visualizar PDF")
        cols = st.columns(4)
        for col, lg in zip(cols, LANGS):
            with col:
                pdf_button(sid, fl[i].meta["flight_index"], lg, LANGS[lg], key=f"o_{sid}_{i}_{lg}")
    st.markdown("#### Decisão")
    note = st.text_area("Nota para o cliente (visível no portal)", value=s.get("review_note") or "", key=f"note_{sid}")
    a, b = st.columns(2)
    if a.button("✅ Aprovar e libertar", type="primary", key=f"ap_{sid}", disabled=not fl):
        wf.review(sid, True, note)
        sent = notify_released_for(s["client_id"])
        st.success("Aprovado." + (" Cliente notificado por email." if sent else
                                   " O cliente vê o relatório quando a subscrição estiver ativa."))
        st.rerun()
    if b.button("↩️ Devolver ao cliente", key=f"rj_{sid}"):
        wf.review(sid, False, note)
        st.rerun()


def owner_review():
    st.title(tr("p_review"))
    queue = wf.submissions(status="pending_review") + wf.submissions(status="error")
    if not queue:
        st.success("Sem relatórios a aguardar aprovação.")
        return
    names = {c["id"]: c["name"] for c in wf.clients()}
    sid = st.selectbox("Fila", [s["id"] for s in queue],
                       format_func=lambda i: next(f"#{s['id']} · {names.get(s['client_id'], s['client_id'])} · "
                                                  f"{s['registration']} · {s['uploaded_at'][:16]} · {s['status']} · "
                                                  f"nível máx. {s['max_level']}" for s in queue if s["id"] == i))
    submission_detail(sid)


def owner_subs():
    st.title(tr("p_subs"))
    subs = wf.submissions()
    if not subs:
        st.info(tr("nothing_yet"))
        return
    df = pd.DataFrame(subs)
    c1, c2 = st.columns(2)
    fc = c1.multiselect("Cliente", sorted(df.client_id.unique()))
    fs = c2.multiselect("Estado", list(wf.STATUSES))
    if fc:
        df = df[df.client_id.isin(fc)]
    if fs:
        df = df[df.status.isin(fs)]
    st.dataframe(df[["id", "client_id", "registration", "filename", "uploaded_at", "status", "n_flights", "max_level",
                     "n_events", "reviewed_at"]], use_container_width=True, hide_index=True)
    if len(df):
        sid = st.selectbox("Abrir submissão", df.id.tolist())
        submission_detail(int(sid))


def owner_clients():
    st.title(tr("p_clients"))
    cls = wf.clients()
    if cls:
        st.dataframe(pd.DataFrame([{
            "ID": c["id"], "Nome": c["name"], "Email": c["email"], "Idioma": c["lang"],
            "Módulos": ", ".join(wf.modules(c)), "Pagamento": c["billing"],
            "Subscrição": "ativa" if sub_ok(c) else "inativa", "Até": c["sub_until"] or "",
            "Aeronaves": ", ".join(a["registration"] for a in wf.aircraft(c["id"])),
            "Envios": len(wf.submissions(c["id"])), "Ativo": bool(c["active"])} for c in cls]),
            use_container_width=True, hide_index=True)
    opts = ["➕ Novo cliente"] + [c["id"] for c in cls]
    pick = st.selectbox("Editar", opts)
    cur = wf.client(pick) if pick != opts[0] else {}
    with st.form("cl"):
        c1, c2, c3 = st.columns(3)
        cid = c1.text_input("ID (curto, sem espaços)", value=cur.get("id", ""), disabled=bool(cur))
        name = c2.text_input("Nome do operador", value=cur.get("name", ""))
        email = c3.text_input("Email de login", value=cur.get("email") or "")
        c4, c5, c6 = st.columns(3)
        lang = c4.selectbox("Idioma", list(LANGS), index=list(LANGS).index(cur.get("lang") or "en"),
                            format_func=lambda k: LANGS[k])
        mods = c5.multiselect("Módulos licenciados", MODULE_KEYS, default=wf.modules(cur) if cur else ["FDM"])
        billing = c6.selectbox("Pagamento", ["manual", "stripe", "both"],
                               index=["manual", "stripe", "both"].index(cur.get("billing") or "manual"),
                               format_func=lambda k: {"manual": "Fatura (manual)", "stripe": "Stripe", "both": "Ambos"}[k])
        c7, c8, c9 = st.columns(3)
        sub_active = c7.checkbox("Subscrição paga (manual)", value=bool(cur.get("sub_active")))
        until = c8.date_input("Válida até", value=date.fromisoformat(cur["sub_until"]) if cur.get("sub_until") else None)
        active = c9.checkbox("Conta ativa", value=bool(cur.get("active", 1)))
        c10, c11 = st.columns(2)
        stripe_email = c10.text_input("Email no Stripe (se diferente)", value=cur.get("stripe_email") or "")
        plink = c11.text_input("Link de pagamento Stripe (opcional)", value=cur.get("payment_link") or "")
        newpw = st.text_input("Nova palavra-passe (vazio = manter; 'gerar' = aleatória)", type="default")
        if st.form_submit_button("Guardar", type="primary"):
            key = cur.get("id") or cid.strip().lower().replace(" ", "-")
            if not key or not name:
                st.error("ID e nome são obrigatórios.")
            else:
                pw_hash = None
                if newpw == "gerar":
                    newpw = secrets.token_urlsafe(10)
                if newpw:
                    pw_hash = wf.hash_pw(newpw)
                was_ok = bool(cur) and sub_ok(cur)
                wf.upsert_client(key, name=name, email=email or None, lang=lang, modules=mods, billing=billing,
                                 sub_active=int(sub_active), sub_until=until.isoformat() if until else "",
                                 stripe_email=stripe_email or "", payment_link=plink or "", active=int(active),
                                 pw_hash=pw_hash)
                wf.audit("owner", "client_save", key)
                msg = "Guardado."
                if newpw:
                    msg += f" Palavra-passe: `{newpw}` (enviar ao cliente por canal seguro; não volta a ser mostrada)."
                if not was_ok and sub_ok(wf.client(key)):
                    n = notify_released_for(key)
                    if n:
                        msg += f" {n} relatório(s) libertado(s) e cliente notificado."
                st.success(msg)
    if cur:
        st.markdown("#### Aeronaves do cliente")
        fleet = wf.aircraft(cur["id"])
        for a in fleet:
            c1, c2, c3 = st.columns([2, 3, 1])
            c1.markdown(f"**{a['registration']}**")
            c2.markdown(a["profile"])
            if c3.button("Remover", key=f"rm_{a['id']}"):
                wf.remove_aircraft(a["id"])
                st.rerun()
        with st.form("ac"):
            c1, c2 = st.columns(2)
            reg = c1.text_input("Matrícula")
            prof = c2.selectbox("Perfil (LFL + eventos)", list_profiles())
            if st.form_submit_button("Adicionar aeronave") and reg:
                wf.add_aircraft(cur["id"], reg, prof)
                st.rerun()


def owner_trends():
    st.title(tr("p_trends"))
    cls = wf.clients()
    if not cls:
        st.info(tr("nothing_yet"))
        return
    cid = st.selectbox("Cliente", [c["id"] for c in cls], format_func=lambda i: wf.client(i)["name"])
    trends(cid)


def owner_analyse():
    st.title(tr("p_analyse"))
    st.caption("Análise interna sem registo no portal do cliente.")
    with st.form("adhoc"):
        c1, c2 = st.columns(2)
        prof = c1.selectbox("Perfil", list_profiles())
        reg = c2.text_input("Matrícula", "")
        up = st.file_uploader(tr("file"))
        if st.form_submit_button(tr("send"), type="primary") and up is not None:
            with st.spinner(tr("processing")):
                try:
                    st.session_state.adhoc = analyse_download(up.getvalue(), prof, {"registration": reg} if reg else {})
                except Exception as ex:  # noqa: BLE001
                    st.error(str(ex))
    fl = st.session_state.get("adhoc") or []
    if fl:
        i = st.selectbox("Voo", range(len(fl)), format_func=lambda k: f"{fl[k].meta['origin']} → {fl[k].meta['destination']}")
        show_flight(fl[i], owner=True)
        lg = st.selectbox(tr("report_lang"), list(LANGS), format_func=lambda k: LANGS[k])
        st.download_button("⬇️ PDF", build_pdf(fl[i], BRAND, lg), f"FDM_{reg}_{i + 1}_{lg}.pdf", "application/pdf")


def owner_profiles():
    st.title(tr("p_profiles"))
    from fdm.decoder import FrameLayout
    from fdm.events import load_event_defs
    from fdm.pipeline import PROFILES_DIR
    prof = st.selectbox("Perfil", list_profiles())
    lay = FrameLayout.load(PROFILES_DIR / prof / "frame_layout.yaml")
    defs, _ = load_event_defs(PROFILES_DIR / prof / "events.yaml")
    st.caption(f"{lay.aircraft_type} · {lay.words_per_second} wps · {lay.storage} · "
               + ("validado" if lay.validated else "NÃO validado"))
    st.dataframe(pd.DataFrame([{"Parâmetro": p.name, "Descrição": p.description, "Unid.": p.units,
                                "Hz": p.rate_hz, "Codificação": p.encoding} for p in lay.params.values()]),
                 use_container_width=True, hide_index=True)
    st.dataframe(pd.DataFrame([{"Código": d.code, "Evento": d.name, "Disparador": d.parameter, "Op": d.op,
                                "N1": d.thresholds[0], "N2": d.thresholds[1], "N3": d.thresholds[2],
                                "Fases": ", ".join(_ph(p, "pt") for p in d.phases), "Condição": d.detection}
                               for d in defs]), use_container_width=True, hide_index=True)


# ================================================================ roteamento
# Duas áreas separadas depois do login: /admin (Vektor) e /client (operador). Cada perfil só recebe
# as suas páginas; um endereço da outra área não existe para essa sessão.
def _home(target):
    def go():
        st.switch_page(target)
    return st.Page(go, title="Home", url_path="home", default=True, visibility="hidden")


def _client_trends():
    st.title(tr("p_trends"))
    if sub_ok(wf.client(CID)):
        trends(CID)
    else:
        st.info(tr("trend_locked"))


if ROLE == "client":
    first = st.Page(client_reports, title=tr("p_reports"), icon="📄", url_path="client")
    nav = st.navigation({tr("nav"): [
        _home(first), first,
        st.Page(client_upload, title=tr("p_upload"), icon="⬆️", url_path="client-upload"),
        st.Page(_client_trends, title=tr("p_trends"), icon="📈", url_path="client-trends"),
        st.Page(client_account, title=tr("p_account"), icon="👤", url_path="client-account"),
    ]})
else:
    pend = len(wf.submissions(status="pending_review")) + len(wf.submissions(status="error"))
    first = st.Page(owner_review, title=tr("p_review") + (f" ({pend})" if pend else ""), icon="✅", url_path="admin")
    nav = st.navigation({"Admin": [
        _home(first), first,
        st.Page(owner_subs, title=tr("p_subs"), icon="🗂️", url_path="admin-submissions"),
        st.Page(owner_clients, title=tr("p_clients"), icon="🏢", url_path="admin-clients"),
        st.Page(owner_trends, title=tr("p_trends"), icon="📈", url_path="admin-trends"),
        st.Page(owner_analyse, title=tr("p_analyse"), icon="🔬", url_path="admin-analyse"),
        st.Page(owner_profiles, title=tr("p_profiles"), icon="✈️", url_path="admin-profiles"),
    ]})
nav.run()
