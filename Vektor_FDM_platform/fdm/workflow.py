"""
Fluxo comercial do portal FDM:

    cliente envia o download -> análise automática -> revisão do dono (aprovar / devolver)
    -> relatório disponível para download quando aprovado E com subscrição ativa.

Tudo fica guardado na pasta FDM_DATA (disco persistente do servidor): base de dados SQLite,
ficheiros originais, análises e PDFs gerados. Só o dono vê tudo; cada cliente vê apenas o seu.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import gzip
import pickle
import secrets
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DATA = Path(os.environ.get("FDM_DATA", Path(__file__).resolve().parents[1] / "data"))
DB = DATA / "workflow.db"
UPLOADS, ANALYSES, REPORTS = DATA / "uploads", DATA / "analyses", DATA / "reports"

STATUSES = ("processing", "pending_review", "approved", "rejected", "error")

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE, pw_hash TEXT, lang TEXT DEFAULT 'en',
    modules TEXT DEFAULT '["FDM"]', billing TEXT DEFAULT 'manual', sub_active INTEGER DEFAULT 0,
    sub_until TEXT, stripe_email TEXT, payment_link TEXT, active INTEGER DEFAULT 1, created_at TEXT
);
CREATE TABLE IF NOT EXISTS aircraft (
    id INTEGER PRIMARY KEY AUTOINCREMENT, client_id TEXT NOT NULL, registration TEXT NOT NULL,
    profile TEXT NOT NULL, UNIQUE(client_id, registration)
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, client_id TEXT NOT NULL, registration TEXT, profile TEXT,
    filename TEXT, raw_path TEXT, size_bytes INTEGER, notes TEXT, uploaded_at TEXT, status TEXT,
    n_flights INTEGER DEFAULT 0, max_level INTEGER DEFAULT 0, n_events INTEGER DEFAULT 0, summary TEXT,
    error TEXT, reviewed_at TEXT, review_note TEXT, released_notified INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, actor TEXT, action TEXT, detail TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def conn() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def audit(actor: str, action: str, detail: str = "") -> None:
    with conn() as c:
        c.execute("INSERT INTO audit (at, actor, action, detail) VALUES (?,?,?,?)", (_now(), actor, action, detail))


# ---------------- Palavras-passe ----------------
def hash_pw(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2${salt}${h}"


def check_pw(pw: str, stored: str | None) -> bool:
    if not stored:
        return False
    if stored.startswith("pbkdf2$"):
        _, salt, h = stored.split("$", 2)
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex(), h)
    return hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), stored)  # contas antigas (FDM_CLIENTS)


# ---------------- Clientes ----------------
def clients() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM clients ORDER BY name")]


def client(cid: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None


def find_login(user: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM clients WHERE (id=? OR lower(email)=lower(?)) AND active=1", (user, user)).fetchone()
        return dict(r) if r else None


def upsert_client(cid: str, **f) -> None:
    f = {k: v for k, v in f.items() if v is not None}
    if "modules" in f and not isinstance(f["modules"], str):
        f["modules"] = json.dumps(f["modules"])
    with conn() as c:
        if c.execute("SELECT 1 FROM clients WHERE id=?", (cid,)).fetchone():
            if f:
                c.execute(f"UPDATE clients SET {', '.join(k + '=?' for k in f)} WHERE id=?", (*f.values(), cid))
        else:
            f.setdefault("name", cid)
            f["created_at"] = _now()
            cols = ["id", *f]
            c.execute(f"INSERT INTO clients ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", (cid, *f.values()))


def import_env_clients() -> None:
    """Migra contas antigas definidas em FDM_CLIENTS (JSON) para a base de dados."""
    try:
        env = json.loads(os.environ.get("FDM_CLIENTS", "{}"))
    except json.JSONDecodeError:
        return
    for cid, d in env.items():
        if not client(cid):
            upsert_client(cid, name=d.get("name", cid), email=d.get("email"), pw_hash=d.get("password_sha256"),
                          modules=d.get("modules", ["FDM"]), lang=d.get("lang", "en"))


def modules(cl: dict) -> list[str]:
    try:
        return [m.upper() for m in json.loads(cl.get("modules") or '["FDM"]')]
    except json.JSONDecodeError:
        return ["FDM"]


def subscription_ok(cl: dict, stripe_check=None) -> bool:
    """Subscrição ativa: marcação manual válida (com data limite opcional) ou Stripe ativo."""
    if cl.get("sub_active"):
        until = cl.get("sub_until")
        if not until or until >= date.today().isoformat():
            return True
    if cl.get("billing") in ("stripe", "both") and stripe_check:
        return bool(stripe_check(cl.get("stripe_email") or cl.get("email")))
    return False


# ---------------- Aeronaves ----------------
def aircraft(cid: str | None = None) -> list[dict]:
    with conn() as c:
        q = "SELECT * FROM aircraft" + (" WHERE client_id=?" if cid else "") + " ORDER BY registration"
        return [dict(r) for r in c.execute(q, (cid,) if cid else ())]


def add_aircraft(cid: str, reg: str, profile: str) -> None:
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO aircraft (client_id, registration, profile) VALUES (?,?,?)",
                  (cid, reg.upper().strip(), profile))


def remove_aircraft(aid: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM aircraft WHERE id=?", (aid,))


# ---------------- Submissões ----------------
def create_submission(cid: str, reg: str, profile: str, filename: str, raw: bytes, notes: str = "") -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = UPLOADS / cid / reg
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{stamp}_{Path(filename).name}"
    path.write_bytes(raw)
    with conn() as c:
        cur = c.execute(
            "INSERT INTO submissions (client_id, registration, profile, filename, raw_path, size_bytes, notes,"
            " uploaded_at, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, reg, profile, filename, str(path), len(raw), notes, _now(), "processing"))
        return cur.lastrowid


def submission(sid: int) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else None


def submissions(cid: str | None = None, status: str | None = None) -> list[dict]:
    q, a = "SELECT * FROM submissions WHERE 1=1", []
    if cid:
        q += " AND client_id=?"
        a.append(cid)
    if status:
        q += " AND status=?"
        a.append(status)
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY id DESC", a)]


def update_submission(sid: int, **f) -> None:
    with conn() as c:
        c.execute(f"UPDATE submissions SET {', '.join(k + '=?' for k in f)} WHERE id=?", (*f.values(), sid))


def process(sid: int) -> list:
    """Corre a análise de uma submissão e guarda o resultado. Devolve a lista de voos."""
    from .pipeline import analyse_download
    s = submission(sid)
    try:
        raw = Path(s["raw_path"]).read_bytes()
        flights = analyse_download(raw, s["profile"], {"registration": s["registration"]})
        ANALYSES.mkdir(parents=True, exist_ok=True)
        for fa in flights:  # a série completa do download já está em fa.native (recortada por voo)
            fa.decoded.data = {}
        with gzip.open(ANALYSES / f"{sid}.pkl.gz", "wb", compresslevel=5) as f:
            pickle.dump(flights, f, protocol=pickle.HIGHEST_PROTOCOL)
        for old in REPORTS.glob(f"{sid}_*.pdf"):
            old.unlink()
        summary = [{"i": fa.meta["flight_index"], "origin": fa.meta.get("origin"), "destination": fa.meta.get("destination"),
                    "air_min": fa.meta.get("block_air_min"), "max_level": fa.risk["max_level"], "n_events": len(fa.events)}
                   for fa in flights]
        update_submission(sid, status="pending_review" if flights else "error", n_flights=len(flights),
                          max_level=max([x["max_level"] for x in summary], default=0),
                          n_events=sum(x["n_events"] for x in summary), summary=json.dumps(summary),
                          error=None if flights else "Nenhum voo encontrado no ficheiro")
        return flights
    except Exception as ex:  # noqa: BLE001
        update_submission(sid, status="error", error=str(ex)[:500])
        return []


def flights(sid: int) -> list:
    p = ANALYSES / f"{sid}.pkl.gz"
    if not p.exists():
        return []
    with gzip.open(p, "rb") as f:
        return pickle.load(f)


def report_pdf(sid: int, idx: int, lang: str, company: str = "Vektor FDM") -> bytes:
    """PDF de um voo da submissão, gerado uma vez por idioma e guardado em cache."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    p = REPORTS / f"{sid}_{idx}_{lang}.pdf"
    if p.exists():
        return p.read_bytes()
    from .report import build_pdf
    fl = [f for f in flights(sid) if f.meta["flight_index"] == idx]
    if not fl:
        raise FileNotFoundError("Voo não encontrado")
    pdf = build_pdf(fl[0], company, lang)
    p.write_bytes(pdf)
    return pdf


def review(sid: int, approve: bool, note: str, actor: str = "owner") -> None:
    update_submission(sid, status="approved" if approve else "rejected", reviewed_at=_now(), review_note=note)
    audit(actor, "approve" if approve else "return", f"submission {sid}: {note}")
    if approve:
        from . import storage
        s = submission(sid)
        for fa in flights(sid):
            storage.save(fa, s["client_id"])


def release_notifications(cid: str) -> int:
    """Avisa o cliente dos relatórios aprovados ainda não notificados, se a subscrição estiver ativa."""
    from . import notify
    cl = client(cid)
    if not cl or not subscription_ok(cl, notify.stripe_active):
        return 0
    n = 0
    for s in submissions(cid, "approved"):
        if not s["released_notified"]:
            notify.client_released(s, cl)
            update_submission(s["id"], released_notified=1)
            n += 1
    return n
