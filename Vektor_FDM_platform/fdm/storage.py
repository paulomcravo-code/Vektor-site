"""Histórico de voos e eventos (SQLite no MVP; PostgreSQL em produção)."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_DATA = Path(os.environ.get("FDM_DATA", Path(__file__).resolve().parents[1] / "data"))
DB_PATH = Path(os.environ.get("FDM_DB", _DATA / "fdm.sqlite"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client TEXT, registration TEXT, aircraft_type TEXT, flight_no TEXT, flight_date TEXT,
    origin TEXT, destination TEXT, profile TEXT, duration_s REAL, quality_pct REAL,
    max_level INTEGER, risk_index INTEGER, n_events INTEGER, uploaded_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id INTEGER REFERENCES flights(id) ON DELETE CASCADE,
    event_id TEXT, name TEXT, category TEXT, level INTEGER, peak REAL, units TEXT,
    phase TEXT, peak_t REAL
);
"""


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript(SCHEMA)
    return c


def save(fa, client: str = "default") -> int:
    m = fa.meta
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO flights (client, registration, aircraft_type, flight_no, flight_date, origin, destination,"
            " profile, duration_s, quality_pct, max_level, risk_index, n_events, uploaded_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (client, m.get("registration"), m["aircraft_type"], m.get("flight_no"), m.get("flight_date"),
             m.get("origin"), m.get("destination"), m["profile"], m["duration_s"], m["quality_pct"],
             fa.risk["max_level"], fa.risk["risk_index"], len(fa.events), datetime.now(timezone.utc).isoformat()))
        fid = cur.lastrowid
        c.executemany(
            "INSERT INTO events (flight_id, event_id, name, category, level, peak, units, phase, peak_t)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            [(fid, e.id, e.name, e.category, e.level, e.peak, e.units, e.phase, e.peak_t) for e in fa.events])
    return fid


def flights(client: str = "default") -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql_query("SELECT * FROM flights WHERE client=? ORDER BY flight_date, id", c, params=(client,))


def events(client: str = "default") -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql_query(
            "SELECT e.*, f.registration, f.flight_date, f.destination FROM events e"
            " JOIN flights f ON f.id = e.flight_id WHERE f.client=?", c, params=(client,))
