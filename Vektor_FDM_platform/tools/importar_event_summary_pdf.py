"""
Importa um "Event Set Summary" em PDF (Scaled Analytics) para events.yaml.

Uso: python tools/importar_event_summary_pdf.py Event_Set_Summary.pdf event_sets/B737.yaml "Boeing 737-700 BBJ"

O resumo em PDF traz, por evento, o disparador e o limiar/duração de cada nível (High, Med, Low),
mas NÃO traz o operador (> ou <), as fases de voo nem a condição de deteção. Esses três elementos são
inferidos a partir do nome do evento e da ordem dos limiares, e ficam marcados com inferred: true.
Para definições exatas, usar a exportação "Event Set Details" com tools/importar_event_set.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pdfplumber
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.importar_event_set import CATEGORY, MITIG  # noqa: E402


def _num(x: str):
    try:
        return float(x.strip())
    except (ValueError, AttributeError):
        return None


def _op(name: str, hi, md, lo) -> str:
    vals = [v for v in (lo, md, hi) if v is not None]
    if len(set(vals)) >= 2:
        return ">" if vals[-1] > vals[0] else "<"
    n = name.lower()
    if n.startswith(("low ", "late ")) or "disengaged late" in n or "early" in n:
        return "<"
    return ">"


def _phases(name: str) -> list[str]:
    n = name.lower()
    ph: list[str] = []

    def add(*p):
        for x in p:
            if x not in ph:
                ph.append(x)
    if "taxi" in n or "on ground" in n:
        add("TAXI_OUT", "TAXI_IN")
    if "rejected takeoff" in n:
        add("TAKEOFF")
    if "takeoff configuration" in n:
        add("TAXI_OUT", "TAKEOFF")
    if "after takeoff" in n:
        add("INITIAL_CLIMB")
    elif "at takeoff" in n:
        add("TAKEOFF")
    elif any(k in n for k in ("rotation", "takeoff or go around")):
        add("TAKEOFF", "INITIAL_CLIMB")
    if "initial climb" in n:
        add("INITIAL_CLIMB")
    if "during climb" in n:
        add("INITIAL_CLIMB", "CLIMB")
    if any(k in n for k in ("on approach", "short final", "late landing flap", "level flight below")):
        add("APPROACH")
    if any(k in n for k in ("touchdown", "flare", "at landing", "on landing", "long landing", "braking", "in reverse")):
        add("LANDING")
    if "in cruise" in n:
        add("CRUISE")
    if "in flight" in n:
        add("INITIAL_CLIMB", "CLIMB", "CRUISE", "DESCENT", "APPROACH")
    if "go around" in n:
        add("GO_AROUND")
    return ph


def _band(name: str) -> str:
    """Faixa de altura no nome do evento -> condição sobre Height Above Airfield."""
    m = re.search(r"between (\d+) ft and (\d+) ft", name, re.I)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        return f"[Height Above Airfield] >= {a} AND [Height Above Airfield] < {b}"
    m = re.search(r"below (\d+) ft", name, re.I)
    if m:
        return f"[Height Above Airfield] < {int(m.group(1))}"
    m = re.search(r"above (\d+) ft", name, re.I)
    if m:
        return f"[Height Above Airfield] > {int(m.group(1))}"
    return ""


NEEDS_DETAILS = ("rejected takeoff", "retraction", "engaged", "disengaged", "gear extension above", "speed exceeded",
                 "above idle thrust", "low power", "late landing", "in turn", "long landing", "tire limit", "in reverse",
                 "gear not locked", "slope", "localizer", "glideslope", "overweight", "mach", "flap", "long flare")
DETAILS_REF = "[Event Set Details definition] > 0"


def needs_details(name: str, trig: str) -> bool:
    """Eventos cuja deteção depende de uma mudança de estado ou de condições que o nome não descreve."""
    n = name.lower()
    return trig in ("Height Above Airfield", "Touchdown Distance") or any(k in n for k in NEEDS_DETAILS)


def parse(pdf_path: str) -> list[dict]:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            for tb in pg.extract_tables():
                for r in tb:
                    r = [(c or "").replace("\n", " ").strip() for c in r]
                    if r and r[0] and not r[0].startswith("Event"):
                        rows.append(r)
    out = []
    for r in rows:
        code, name, trig = re.sub(r"\s+", "", r[0]), r[1], r[2]
        hi, hid, lo, lod, md, mdd = (_num(x) for x in r[3:9])
        if trig.startswith("[") and trig.endswith("]") and trig.count("[") == 1:
            trig = trig.strip("[]").strip()
        op = _op(name, hi, md, lo)
        det = DETAILS_REF if needs_details(name, trig) else _band(name)
        n = name.lower()
        if det != DETAILS_REF and "at takeoff" in n:
            det = "[AIR GROUND] > 0.5"  # ainda no solo (rotação)
        if det != DETAILS_REF and any(k in n for k in ("at touchdown", "on landing")):
            det = "[AIR GROUND] > 0.5 AND [AIR GROUND(-4)] < 0.5"  # primeiros 4 s após o toque
        cat = next((c for k, c in CATEGORY if k.lower() in name.lower()), "Operação")
        out.append({
            "id": code, "code": code, "name": name, "category": cat, "parameter": trig, "op": op,
            "mode": "min" if op == "<" else "max",
            "thresholds": [lo, md, hi], "durations": [lod or 0.0, mdd or 0.0, hid or 0.0],
            "phases": _phases(name), "conditions": [], "detection": det,
            "description": "", "inferred": True, "mitigation": MITIG,
        })
    return out


def main(src: str, dst: str, aircraft: str) -> None:
    evs = parse(src)
    hdr = (f"# Importado de {Path(src).name} (Event Set Summary, PDF)\n# Aeronave: {aircraft}\n"
           "# ATENÇÃO: operador, fases e faixas de altura INFERIDOS do nome do evento (inferred: true).\n"
           "# Confirmar com a exportação 'Event Set Details' do fornecedor antes de uso operacional.\n")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(hdr + yaml.safe_dump({"aircraft": aircraft, "source": Path(src).name, "events": evs},
                                              allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    trig = sorted({e["parameter"] for e in evs})
    nd = sum(e["detection"] == DETAILS_REF for e in evs)
    print(f"{len(evs)} eventos; {nd} precisam da definição completa (Event Set Details); "
          f"{sum(bool(e['detection']) and e['detection'] != DETAILS_REF for e in evs)} com faixa de altura; "
          f"{sum(bool(e['phases']) for e in evs)} com fases; {len(trig)} parâmetros disparadores")


if __name__ == "__main__":
    main(*sys.argv[1:4])
