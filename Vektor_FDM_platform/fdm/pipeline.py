"""Orquestra: descodificar -> separar voos -> derivados -> fases -> eventos -> resumo de risco.

Um download de QAR/MQAR contém normalmente vários voos (dias ou semanas de gravação).
analyse_download() devolve uma análise por voo; analyse() mantém a interface antiga
e devolve o voo mais longo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import geo
from .decoder import DecodeResult, FrameLayout, decode, to_dataframe
from .events import Event, EventDef, detect_events, load_event_defs, risk_summary
from .expr import MissingParams, evaluate
from .phases import air_mask, detect_phases

PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"
ABS_RE = re.compile(r"^\s*abs\(\s*\[([^\]]+)\]\s*\)\s*$", re.I)
RATE_RE = re.compile(r"^\s*(abs_)?rate(_wrap)?\(\s*\[([^\]]+)\]\s*\)\s*$", re.I)


@dataclass
class FlightAnalysis:
    meta: dict
    decoded: DecodeResult
    df: pd.DataFrame
    phase: pd.Series
    marks: dict
    events: list[Event]
    stats: pd.DataFrame
    risk: dict
    defs: list[EventDef]
    native: dict | None = None
    mapping: dict | None = None


def list_profiles() -> list[str]:
    return sorted(p.name for p in PROFILES_DIR.iterdir() if (p / "frame_layout.yaml").exists())


def _derive(df: pd.DataFrame, native: dict, layout: FrameLayout) -> None:
    for name, expr in layout.derived.items():
        r = RATE_RE.match(expr)
        if r and r.group(3) in native:
            src = native[r.group(3)].dropna()
            v = src.values.astype(float)
            if r.group(2):  # ângulo com salto 180/-180 (proa)
                v = np.degrees(np.unwrap(np.radians(v)))
            rate = np.gradient(v, src.index.values) if len(v) > 2 else np.zeros_like(v)
            if r.group(1):
                rate = np.abs(rate)
            native[name] = pd.Series(rate, index=src.index, name=name)
            df[name] = np.interp(df.index.values, src.index.values, rate)
            continue
        m = ABS_RE.match(expr)
        if m and m.group(1) in native:
            native[name] = native[m.group(1)].abs().rename(name)
            df[name] = df[m.group(1)].abs()
            continue
        try:
            df[name] = np.asarray(evaluate(expr, df), dtype=float)
        except MissingParams:
            pass


def _segments(air: np.ndarray, min_air_s: int = 300, merge_gap_s: int = 120) -> list[tuple[int, int]]:
    """Blocos contínuos no ar (índices na grelha de 1 Hz)."""
    a = np.r_[False, air, False].astype(int)
    d = np.diff(a)
    st, en = np.where(d == 1)[0], np.where(d == -1)[0] - 1
    segs: list[list[int]] = []
    for s, e in zip(st, en):
        if segs and s - segs[-1][1] <= merge_gap_s:
            segs[-1][1] = e
        else:
            segs.append([s, e])
    return [(s, e) for s, e in segs if e - s >= min_air_s]


def _haa(df: pd.DataFrame, alt_col: str, i_lo: int, i_td: int) -> np.ndarray:
    """Height Above Airfield: altitude-pressão menos a do aeródromo de partida (1.ª metade)
    ou de chegada (2.ª metade), ambas medidas no solo."""
    alt = df[alt_col].values
    dep = np.nanmedian(alt[max(0, i_lo - 60):max(1, i_lo - 5)])
    arr = np.nanmedian(alt[i_td + 5:i_td + 60]) if i_td + 10 < len(alt) else alt[i_td]
    mid = (i_lo + i_td) // 2
    out = alt - arr
    out[:mid] = alt[:mid] - dep
    return out


def _position(df: pd.DataFrame, mapping: dict, i: int):
    la, lo = mapping.get("latitude"), mapping.get("longitude")
    if la not in df or lo not in df:
        return None, None
    w = df.iloc[max(0, i - 30):i + 30]
    return float(w[la].median()), float(w[lo].median())


def analyse_download(raw: bytes, profile: str, meta: dict | None = None) -> list[FlightAnalysis]:
    pdir = PROFILES_DIR / profile
    layout = FrameLayout.load(pdir / "frame_layout.yaml")
    defs, phase_cfg = load_event_defs(pdir / "events.yaml")
    for ed in defs:
        if not ed.units and ed.parameter in layout.params:
            ed.units = layout.params[ed.parameter].units
    mapping = phase_cfg.get("mapping", {})
    res = decode(raw, layout)
    full = to_dataframe(res, hz=1.0)
    native_full = dict(res.data)
    _derive(full, native_full, layout)

    air = air_mask(full, phase_cfg).values
    segs = _segments(air)
    flights: list[FlightAnalysis] = []
    for k, (s, e) in enumerate(segs):
        prev_end = segs[k - 1][1] if k else 0
        next_start = segs[k + 1][0] if k + 1 < len(segs) else len(full) - 1
        i0 = max(prev_end + (s - prev_end) // 2 if k else 0, s - 1200)
        i1 = min(e + (next_start - e) // 2 if k + 1 < len(segs) else len(full) - 1, e + 900)
        df = full.iloc[i0:i1 + 1].copy()
        t0, t1 = df.index[0], df.index[-1]
        native = {n: v[(v.index >= t0) & (v.index <= t1 + 0.999)] for n, v in native_full.items()}
        alt_col = mapping.get("altitude")
        if alt_col in df and "Height Above Airfield" not in df:
            df["Height Above Airfield"] = _haa(df, alt_col, s - i0, e - i0)
        phase, marks = detect_phases(df, phase_cfg)
        native["VS_FPM"] = df["VS_FPM"]
        events, stats = detect_events(df, native, phase, defs)

        m = dict(meta or {})
        lat0, lon0 = _position(full, mapping, s)
        lat1, lon1 = _position(full, mapping, e)
        dep, arr = geo.nearest_airport(lat0, lon0), geo.nearest_airport(lat1, lon1)
        m.setdefault("origin", dep["icao"] if dep else (f"{lat0:.2f}, {lon0:.2f}" if lat0 is not None else "-"))
        m.setdefault("destination", arr["icao"] if arr else (f"{lat1:.2f}, {lon1:.2f}" if lat1 is not None else "-"))
        m.update(
            aircraft_type=layout.aircraft_type, profile=profile, duration_s=float(t1 - t0),
            quality_pct=res.quality_pct, sync_losses=res.sync_losses, n_params=len(res.data),
            flight_index=k + 1, flights_in_download=len(segs), rec_start_s=float(t0),
            origin_name=dep["name"] if dep else "", destination_name=arr["name"] if arr else "",
            layout_validated=layout.validated, layout_notes=layout.notes,
            download_duration_s=res.duration_s,
        )
        if "liftoff_s" in marks and "touchdown_s" in marks:
            m["block_air_min"] = round((marks["touchdown_s"] - marks["liftoff_s"]) / 60, 1)
        if alt_col in df:
            m["max_alt_ft"] = float(np.nanmax(df[alt_col].values))
        flights.append(FlightAnalysis(m, res, df, phase, marks, events, stats, risk_summary(events),
                                      defs, native, mapping))
    return flights


def analyse(raw: bytes, profile: str, meta: dict | None = None) -> FlightAnalysis:
    flights = analyse_download(raw, profile, meta)
    if not flights:
        raise ValueError("Nenhum voo encontrado no ficheiro (sem período no ar com mais de 5 minutos).")
    return max(flights, key=lambda f: f.meta.get("block_air_min", 0))
