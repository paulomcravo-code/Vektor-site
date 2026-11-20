"""Notificações por email (SMTP) e verificação de subscrições no Stripe.

Variáveis de ambiente (todas opcionais; sem elas a plataforma funciona e só não envia emails
nem consulta o Stripe):
    SMTP_HOST, SMTP_PORT (465 SSL ou 587 STARTTLS), SMTP_USER, SMTP_PASS, SMTP_FROM
    OWNER_EMAIL       destinatário dos avisos de novos envios (ex.: fdm@vektor.aero)
    PORTAL_URL        endereço público do portal (ex.: https://fdm.vektor.aero)
    STRIPE_SECRET_KEY chave secreta (sk_live_...) para confirmar subscrições ativas
    STRIPE_PAYMENT_LINK link de pagamento por omissão (Stripe Payment Link)
"""
from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage

PORTAL = os.environ.get("PORTAL_URL", "https://fdm.vektor.aero")

MSG = {
    "new_upload": {
        "subject": "[Vektor FDM] Novo envio de {client} · {reg}",
        "body": "Novo download recebido de {client} ({reg}, {file}).\nEstado: {status}. Voos: {n}. Risco máximo: nível {lvl}.\n\n"
                "Rever e aprovar: {url}\n"},
    "released": {
        "pt": ("[Vektor FDM] Relatório disponível · {reg}",
               "Olá,\n\nO relatório FDM de {reg} ({file}) está disponível para download no portal: {url}\n\nVektor · vektor.aero"),
        "en": ("[Vektor FDM] Report available · {reg}",
               "Hello,\n\nThe FDM report for {reg} ({file}) is available for download on the portal: {url}\n\nVektor · vektor.aero"),
        "fr": ("[Vektor FDM] Rapport disponible · {reg}",
               "Bonjour,\n\nLe rapport FDM de {reg} ({file}) est disponible au téléchargement sur le portail : {url}\n\nVektor · vektor.aero"),
        "es": ("[Vektor FDM] Informe disponible · {reg}",
               "Hola,\n\nEl informe FDM de {reg} ({file}) está disponible para descarga en el portal: {url}\n\nVektor · vektor.aero"),
    },
}


def send_mail(to: str | None, subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    if not host or not to:
        return False
    port = int(os.environ.get("SMTP_PORT", "465"))
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", user or "fdm@vektor.aero")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
                if user:
                    s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                if user:
                    s.login(user, pw)
                s.send_message(msg)
        return True
    except Exception:  # noqa: BLE001  (um email falhado nunca bloqueia o fluxo)
        return False


def owner_new_upload(sub: dict, client_name: str) -> bool:
    m = MSG["new_upload"]
    k = dict(client=client_name, reg=sub["registration"], file=sub["filename"], status=sub["status"],
             n=sub.get("n_flights", 0), lvl=sub.get("max_level", 0), url=PORTAL)
    return send_mail(os.environ.get("OWNER_EMAIL"), m["subject"].format(**k), m["body"].format(**k))


def client_released(sub: dict, cl: dict) -> bool:
    subj, body = MSG["released"].get(cl.get("lang") or "en", MSG["released"]["en"])
    k = dict(reg=sub["registration"], file=sub["filename"], url=PORTAL)
    return send_mail(cl.get("email"), subj.format(**k), body.format(**k))


# ---------------- Stripe (API REST, sem dependências) ----------------
_cache: dict[str, tuple[float, bool]] = {}


def _stripe_get(path: str, params: dict) -> dict:
    key = os.environ["STRIPE_SECRET_KEY"]
    url = f"https://api.stripe.com/v1/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode()})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def stripe_active(email: str | None, ttl: int = 600) -> bool:
    """Verdadeiro se o cliente com este email tem uma subscrição Stripe ativa ou em período experimental."""
    if not email or not os.environ.get("STRIPE_SECRET_KEY"):
        return False
    hit = _cache.get(email.lower())
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    ok = False
    try:
        for cust in _stripe_get("customers", {"email": email, "limit": 10}).get("data", []):
            subs = _stripe_get("subscriptions", {"customer": cust["id"], "status": "all", "limit": 20}).get("data", [])
            if any(s.get("status") in ("active", "trialing") for s in subs):
                ok = True
                break
    except Exception:  # noqa: BLE001  (Stripe indisponível: fica a marcação manual)
        ok = False
    _cache[email.lower()] = (time.time(), ok)
    return ok


def payment_link(cl: dict) -> str | None:
    link = cl.get("payment_link") or os.environ.get("STRIPE_PAYMENT_LINK")
    if link and cl.get("email"):
        sep = "&" if "?" in link else "?"
        link = f"{link}{sep}prefilled_email={urllib.parse.quote(cl['email'])}"
    return link
