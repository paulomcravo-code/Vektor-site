"""
Motor de eventos FDM: compara cada parâmetro com três limiares
(baixo, médio, alto) e classifica o risco em nível 1, 2 ou 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .expr import MissingParams, evaluate, refs

LEVEL_LABEL = {0: "Normal", 1: "Nível 1 · Baixo", 2: "Nível 2 · Médio", 3: "Nível 3 · Alto"}
LEVEL_COLOR = {0: "#2E8B57", 1: "#E3B505", 2: "#E07A1F", 3: "#C62828"}


@dataclass
class EventDef:
    id: str
    name: str
    parameter: str
    mode: str  # max | min | abs_max
    thresholds: list  # [nível 1, nível 2, nível 3]; None = nível não definido
    phases: list[str]
    min_duration_s: float = 1.0
    durations: list | None = None  # duração mínima por nível (s); por omissão min_duration_s
    op: str = ""  # ">" ou "<"; derivado de mode se vazio
    code: str = ""
    detection: str = ""  # condição original do fornecedor (texto)
    conditions: list[dict] = field(default_factory=list)
    category: str = ""
    units: str = ""
    description: str = ""
    mitigation: dict = field(default_factory=dict)


@dataclass
class Event:
    id: str
    name: str
    parameter: str
    level: int
    start_s: float
    end_s: float
    peak: float
    peak_t: float
    phase: str
    thresholds: list[float]
    units: str
    category: str
    mitigation: list[str]


def load_event_defs(path: str | Path) -> tuple[list[EventDef], dict]:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    defs = []
    for e in cfg["events"]:
        defs.append(EventDef(
            id=e["id"], name=e["name"], parameter=e["parameter"], mode=e.get("mode", "max"),
            thresholds=[None if x is None else float(x) for x in e["thresholds"]],
            phases=e.get("phases", []),
            min_duration_s=float(e.get("min_duration_s", 1)), conditions=e.get("conditions", []),
            durations=e.get("durations"), op=e.get("op", ""), code=e.get("code", ""),
            detection=e.get("detection", ""),
            category=e.get("category", ""), units=e.get("units", ""),
            description=e.get("description", ""),
            mitigation={int(k): v for k, v in e.get("mitigation", {}).items()},
        ))
    return defs, cfg.get("phase_detection", {})


def _cmp(a: np.ndarray, op: str, b: float) -> np.ndarray:
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b}[op]


def _op(ed: EventDef) -> str:
    return ed.op or ("<" if ed.mode == "min" else ">")


def _defined(ed: EventDef) -> list[tuple[int, float, float]]:
    """[(nível, limiar, duração)] só para os níveis definidos."""
    out = []
    for i, th in enumerate(ed.thresholds, start=1):
        if th is None:
            continue
        dur = ed.min_duration_s
        if ed.durations and i <= len(ed.durations) and ed.durations[i - 1] is not None:
            dur = float(ed.durations[i - 1])
        out.append((i, float(th), dur))
    return out


def _hit(x, op: str, th: float):
    return x < th if op == "<" else x > th


def _level(v: float, ed: EventDef) -> int:
    """Nível pelo valor de pico, sem considerar duração (usado no resumo)."""
    x = abs(v) if ed.mode == "abs_max" else v
    lvl = 0
    for i, th, _ in _defined(ed):
        if _hit(x, _op(ed), th) or x == th:
            lvl = max(lvl, i)
    return lvl


def _longest_run(t: np.ndarray, m: np.ndarray, dt: float) -> float:
    """Maior duração contínua (s) em que m é verdadeiro."""
    if not m.any():
        return -1.0
    idx = np.where(m)[0]
    splits = np.where(np.diff(idx) > 1)[0] + 1
    return max(float(t[g[-1]] - t[g[0]]) for g in np.split(idx, splits))


def detect_events(df: pd.DataFrame, native: dict[str, pd.Series], phase: pd.Series,
                  defs: list[EventDef]) -> tuple[list[Event], pd.DataFrame]:
    events: list[Event] = []
    stats = []
    grid_t = df.index.values
    for ed in defs:
        missing: list[str] = []
        s = native.get(ed.parameter)
        if s is None and ed.parameter in df:
            s = df[ed.parameter]
        if s is None and "[" in ed.parameter:
            try:
                s = pd.Series(evaluate(ed.parameter, df).astype(float), index=df.index, name=ed.parameter)
            except MissingParams as mp:
                missing += mp.names
        elif s is None:
            missing.append(ed.parameter)

        # Máscara de elegibilidade na grelha de 1 Hz (fase + condições adicionais)
        mask = np.ones(len(df), dtype=bool)
        if ed.phases:
            mask &= phase.isin(ed.phases).values
        if ed.detection:
            try:
                mask &= np.nan_to_num(evaluate(ed.detection, df).astype(float)) > 0.5
            except MissingParams as mp:
                missing += [n for n in mp.names if n not in missing]
            except Exception as ex:  # expressão fora do suportado
                missing.append(f"condição não suportada ({ex})")
        else:
            for c in ed.conditions:
                if c["param"] not in df:
                    missing.append(c["param"])
                    continue
                mask &= _cmp(df[c["param"]].values, c["op"], float(c["value"]))
        if missing or s is None:
            stats.append({"id": ed.id, "name": ed.name, "parameter": ed.parameter, "available": False,
                          "missing": sorted(set(missing))})
            continue
        native.setdefault(ed.parameter, s)

        t = s.index.values
        gi = np.clip(np.searchsorted(grid_t, t, side="right") - 1, 0, len(df) - 1)
        elig = mask[gi]
        v = s.values.astype(float)
        x = np.abs(v) if ed.mode == "abs_max" else v
        elig = elig & ~np.isnan(x)

        op = _op(ed)
        levels = _defined(ed)
        if not levels:
            stats.append({"id": ed.id, "name": ed.name, "parameter": ed.parameter, "available": False})
            continue
        if elig.any():
            sel = x[elig]
            peak = float(sel.min() if op == "<" else sel.max())
        else:
            peak = np.nan
        loose = min(l[1] for l in levels) if op == ">" else max(l[1] for l in levels)
        exceed = elig & _hit(x, op, loose)
        dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0

        n_ev = 0
        if exceed.any():
            idx = np.where(exceed)[0]
            # agrupar amostras separadas por menos de 5 s (histerese contra ruído)
            splits = np.where(np.diff(t[idx]) > 5.0)[0] + 1
            for grp in np.split(idx, splits):
                seg = np.arange(grp[0], grp[-1] + 1)
                xs, ts = x[seg], t[seg]
                lvl = 0
                for i, th, dur in levels:
                    run = _longest_run(ts, elig[seg] & _hit(xs, op, th), dt)
                    if run >= 0 and run + dt >= dur:
                        lvl = max(lvl, i)
                if lvl == 0:
                    continue
                j = grp[np.argmin(x[grp])] if op == "<" else grp[np.argmax(x[grp])]
                pv = float(v[j])
                n_ev += 1
                events.append(Event(
                    id=ed.id, name=ed.name, parameter=ed.parameter, level=lvl,
                    start_s=float(t[grp[0]]), end_s=float(t[grp[-1]]), peak=pv, peak_t=float(t[j]),
                    phase=str(phase.iloc[gi[j]]), thresholds=ed.thresholds, units=ed.units,
                    category=ed.category, mitigation=ed.mitigation.get(lvl, []),
                ))
        # classificação do voo para este evento: o nível mais alto efetivamente disparado
        # (o pico sozinho não chega, porque cada nível exige uma duração mínima)
        lvl_peak = max([ev.level for ev in events if ev.id == ed.id and ev.start_s >= (t[0] if len(t) else 0)]
                       [-n_ev:] if n_ev else [0])
        stats.append({
            "id": ed.id, "name": ed.name, "parameter": ed.parameter, "available": True,
            "units": ed.units, "mode": ed.mode, "peak": peak, "level": lvl_peak,
            "L1": ed.thresholds[0], "L2": ed.thresholds[1], "L3": ed.thresholds[2], "op": _op(ed),
            "n_events": n_ev, "category": ed.category,
        })
    events.sort(key=lambda e: (-e.level, e.start_s))
    return events, pd.DataFrame(stats)


def risk_summary(events: list[Event]) -> dict:
    counts = {1: 0, 2: 0, 3: 0}
    for e in events:
        counts[e.level] += 1
    max_lvl = max([e.level for e in events], default=0)
    # Índice de risco do voo: ponderação quadrática para destacar níveis altos
    index = counts[1] * 1 + counts[2] * 4 + counts[3] * 9
    return {"counts": counts, "max_level": max_lvl, "risk_index": index}
