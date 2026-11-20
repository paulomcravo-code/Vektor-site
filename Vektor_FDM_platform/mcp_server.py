"""
Servidor MCP da plataforma Vektor FDM: liga a plataforma ao Claude como connector.

Endereço (a colar no Claude em Definições > Connectors > Adicionar connector personalizado):
    https://fdm.vektor.aero/mcp/<MCP_TOKEN>

O token secreto (variável MCP_TOKEN) faz parte do endereço e dá acesso de dono a todos os dados:
trata-o como uma palavra-passe e muda-o se for exposto. Sem MCP_TOKEN o servidor não arranca.

Executar localmente:  MCP_TOKEN=... uvicorn mcp_server:app --port 8000
"""
from __future__ import annotations

import json
import os
from datetime import date

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fdm import storage
from fdm import workflow as wf
from fdm.i18n import LANGS
from fdm.notify import PORTAL, stripe_active
from fdm.pipeline import list_profiles

TOKEN = os.environ.get("MCP_TOKEN", "")
if len(TOKEN) < 24:
    raise SystemExit("Defina MCP_TOKEN com pelo menos 24 caracteres aleatórios.")
PUBLIC = os.environ.get("PORTAL_URL", PORTAL).rstrip("/")

mcp = FastMCP(
    "Vektor FDM",
    instructions=(
        "Plataforma Vektor FDM (Flight Data Monitoring) do dono da Vektor. Permite ver clientes, aeronaves, "
        "downloads enviados pelos clientes (submissões), eventos FDM por voo com níveis 1/2/3, tendências de frota, "
        "e gerir aprovações e subscrições. Os relatórios só ficam disponíveis ao cliente depois de aprovados e com "
        "subscrição ativa. Confirmar com o utilizador antes de aprovar, devolver, alterar subscrições ou criar contas."),
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
mcp.settings.streamable_http_path = f"/mcp/{TOKEN}"

RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
RW = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _sub_ok(cl: dict) -> bool:
    return wf.subscription_ok(cl, stripe_active)


def _client_row(c: dict) -> dict:
    return {"id": c["id"], "name": c["name"], "email": c["email"], "language": c["lang"],
            "modules": wf.modules(c), "billing": c["billing"], "subscription_active": _sub_ok(c),
            "subscription_until": c["sub_until"] or None, "account_active": bool(c["active"]),
            "aircraft": [a["registration"] for a in wf.aircraft(c["id"])]}


def _sub_row(s: dict) -> dict:
    return {"id": s["id"], "client_id": s["client_id"], "registration": s["registration"], "file": s["filename"],
            "uploaded_at": s["uploaded_at"], "status": s["status"], "flights": s["n_flights"],
            "max_level": s["max_level"], "events": s["n_events"], "profile": s["profile"],
            "review_note": s["review_note"], "error": s["error"]}


@mcp.tool(annotations=RO)
def platform_summary() -> dict:
    """Resumo da plataforma: clientes, subscrições ativas, submissões por estado e fila de aprovação."""
    subs = wf.submissions()
    cls = wf.clients()
    by = {st: sum(1 for s in subs if s["status"] == st) for st in wf.STATUSES}
    return {"clients": len(cls), "active_subscriptions": sum(_sub_ok(c) for c in cls), "submissions_by_status": by,
            "awaiting_review": [_sub_row(s) for s in subs if s["status"] in ("pending_review", "error")][:20],
            "portal": PUBLIC}


@mcp.tool(annotations=RO)
def list_clients() -> list[dict]:
    """Lista todos os clientes com módulos, estado da subscrição e aeronaves."""
    return [_client_row(c) for c in wf.clients()]


@mcp.tool(annotations=RO)
def get_client(client_id: str) -> dict:
    """Detalhe de um cliente, incluindo as últimas submissões."""
    c = wf.client(client_id)
    if not c:
        return {"error": f"Cliente '{client_id}' não existe"}
    return {**_client_row(c), "submissions": [_sub_row(s) for s in wf.submissions(client_id)[:30]]}


@mcp.tool(annotations=RO)
def list_submissions(status: str | None = None, client_id: str | None = None, limit: int = 50) -> list[dict]:
    """Lista downloads enviados. status: processing, pending_review, approved, rejected ou error."""
    return [_sub_row(s) for s in wf.submissions(client_id, status)[:limit]]


@mcp.tool(annotations=RO)
def get_submission(submission_id: int, include_unavailable: bool = False) -> dict:
    """Detalhe de uma submissão: cada voo (origem, destino, tempo no ar) e cada evento FDM detetado
    (nome, nível 1-3, pico, fase, limiares). include_unavailable lista os eventos não avaliados por falta de parâmetros."""
    s = wf.submission(submission_id)
    if not s:
        return {"error": "Submissão não encontrada"}
    out = {**_sub_row(s), "notes": s["notes"], "flights_detail": []}
    for fa in wf.flights(submission_id):
        m = fa.meta
        f = {"flight": m["flight_index"], "origin": m.get("origin"), "destination": m.get("destination"),
             "origin_name": m.get("origin_name"), "destination_name": m.get("destination_name"),
             "airborne_min": m.get("block_air_min"), "max_alt_ft": m.get("max_alt_ft"),
             "risk": fa.risk, "mapping_validated": m.get("layout_validated", True),
             "events": [{"n": i, "code": e.id, "name": e.name, "level": e.level, "peak": round(e.peak, 3),
                         "units": e.units, "phase": e.phase, "thresholds": e.thresholds,
                         "t_from_segment_start_s": round(e.peak_t - fa.df.index[0], 1)}
                        for i, e in enumerate(fa.events, start=1)],
             "events_evaluated": int(fa.stats["available"].sum()), "events_in_programme": len(fa.stats)}
        if include_unavailable:
            miss = fa.stats[~fa.stats["available"]]
            f["not_evaluated"] = [{"name": r["name"], "missing": r.get("missing")} for _, r in miss.iterrows()]
        out["flights_detail"].append(f)
    return out


@mcp.tool(annotations=RO)
def report_pdf_link(submission_id: int, flight: int, language: str = "en") -> dict:
    """Link privado para descarregar o PDF de um voo (language: pt, en, fr ou es). O link inclui o token: não partilhar."""
    if language not in LANGS:
        return {"error": f"language deve ser um de {list(LANGS)}"}
    if not wf.submission(submission_id):
        return {"error": "Submissão não encontrada"}
    return {"url": f"{PUBLIC}/files/{TOKEN}/{submission_id}/{flight}/{language}.pdf"}


@mcp.tool(annotations=RW)
def approve_submission(submission_id: int, note: str = "") -> dict:
    """Aprova o relatório e liberta-o ao cliente (fica visível quando a subscrição estiver ativa; o cliente é avisado por email)."""
    s = wf.submission(submission_id)
    if not s or s["status"] not in ("pending_review", "rejected", "approved"):
        return {"error": "Só se aprovam submissões analisadas (pending_review)."}
    wf.review(submission_id, True, note, actor="claude-connector")
    sent = wf.release_notifications(s["client_id"])
    cl = wf.client(s["client_id"])
    return {"status": "approved", "visible_to_client_now": _sub_ok(cl), "client_notified": bool(sent)}


@mcp.tool(annotations=RW)
def return_submission(submission_id: int, note: str) -> dict:
    """Devolve a submissão ao cliente com uma nota (ex.: ficheiro incompleto, aeronave errada)."""
    if not wf.submission(submission_id):
        return {"error": "Submissão não encontrada"}
    wf.review(submission_id, False, note, actor="claude-connector")
    return {"status": "rejected", "note": note}


@mcp.tool(annotations=RW)
def reprocess_submission(submission_id: int, profile: str | None = None) -> dict:
    """Volta a analisar o ficheiro original (por exemplo depois de atualizar o LFL ou mudar de perfil)."""
    if not wf.submission(submission_id):
        return {"error": "Submissão não encontrada"}
    if profile:
        if profile not in list_profiles():
            return {"error": f"Perfil desconhecido. Disponíveis: {list_profiles()}"}
        wf.update_submission(submission_id, profile=profile)
    wf.update_submission(submission_id, status="processing")
    wf.process(submission_id)
    wf.audit("claude-connector", "reprocess", str(submission_id))
    return _sub_row(wf.submission(submission_id))


@mcp.tool(annotations=RW)
def set_subscription(client_id: str, active: bool, until: str | None = None) -> dict:
    """Marca a subscrição de um cliente como paga (active=true) ou suspensa, com data limite opcional AAAA-MM-DD."""
    if not wf.client(client_id):
        return {"error": "Cliente não existe"}
    if until:
        date.fromisoformat(until)
    wf.upsert_client(client_id, sub_active=int(active), sub_until=until or "")
    wf.audit("claude-connector", "subscription", f"{client_id} active={active} until={until}")
    released = wf.release_notifications(client_id) if active else 0
    return {**_client_row(wf.client(client_id)), "reports_released_now": released}


@mcp.tool(annotations=RW)
def create_client(client_id: str, name: str, email: str, language: str = "en", modules: list[str] | None = None,
                  billing: str = "manual") -> dict:
    """Cria a conta de um cliente e devolve uma palavra-passe inicial (mostrada só uma vez).
    billing: manual (fatura), stripe ou both."""
    if wf.client(client_id):
        return {"error": "Já existe um cliente com esse ID"}
    import secrets
    pw = secrets.token_urlsafe(10)
    wf.upsert_client(client_id, name=name, email=email, lang=language if language in LANGS else "en",
                     modules=modules or ["FDM"], billing=billing, pw_hash=wf.hash_pw(pw))
    wf.audit("claude-connector", "client_create", client_id)
    return {**_client_row(wf.client(client_id)), "initial_password": pw, "portal": PUBLIC}


@mcp.tool(annotations=RW)
def add_aircraft(client_id: str, registration: str, profile: str) -> dict:
    """Associa uma aeronave a um cliente com o perfil de descodificação (LFL + eventos)."""
    if not wf.client(client_id):
        return {"error": "Cliente não existe"}
    if profile not in list_profiles():
        return {"error": f"Perfil desconhecido. Disponíveis: {list_profiles()}"}
    wf.add_aircraft(client_id, registration, profile)
    return {"client_id": client_id, "aircraft": wf.aircraft(client_id)}


@mcp.tool(annotations=RO)
def list_aircraft_profiles() -> list[str]:
    """Perfis de aeronave disponíveis (Data Frame Layout + conjunto de eventos)."""
    return list_profiles()


@mcp.tool(annotations=RO)
def fleet_trends(client_id: str) -> dict:
    """Tendências dos voos aprovados de um cliente: voos, eventos por tipo e nível, taxa de nível 3 por 100 voos."""
    fl, ev = storage.flights(client_id), storage.events(client_id)
    if fl.empty:
        return {"flights": 0}
    by = ev.groupby(["name", "level"]).size().reset_index(name="count").sort_values("count", ascending=False)
    return {"flights": int(len(fl)), "aircraft": sorted(fl["registration"].dropna().unique().tolist()),
            "events": int(len(ev)), "level3_per_100_flights": round(100 * int((ev.level == 3).sum()) / len(fl), 2),
            "by_event": json.loads(by.head(40).to_json(orient="records")),
            "by_route": json.loads(fl.groupby(["origin", "destination"]).size().reset_index(name="flights")
                                   .to_json(orient="records"))}


@mcp.custom_route("/files/{token}/{sid}/{idx}/{lang}.pdf", methods=["GET"])
async def pdf_file(request: Request) -> Response:
    p = request.path_params
    if p["token"] != TOKEN or p["lang"] not in LANGS:
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        pdf = wf.report_pdf(int(p["sid"]), int(p["idx"]), p["lang"])
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "not found"}, status_code=404)
    s = wf.submission(int(p["sid"]))
    name = f"Vektor_FDM_{s['registration']}_{p['sid']}_{p['idx']}_{p['lang']}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})


@mcp.custom_route("/mcp-health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse({"ok": True})


app = mcp.streamable_http_app()
