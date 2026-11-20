"""
Importa um "Event Set Details" (exportação .xls/.xlsx do software FDM do fornecedor)
para o formato events.yaml da plataforma Vektor.

Uso: python tools/importar_event_set.py Event_Set_Details_GLEX.xlsx profiles/glex/events.yaml "Bombardier Global Express"

Mapeamento de níveis: Low -> nível 1, Med -> nível 2, High -> nível 3.
Cada nível mantém o seu limiar e a sua duração mínima. As condições do
"Detection Period" com a forma [Param] op valor (unidas por AND) são
convertidas em condições; as restantes ficam em "detection" para revisão.
Os nomes dos parâmetros ficam como no ficheiro de origem e têm de existir
com o mesmo nome no frame_layout.yaml (LFL).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import yaml

PHASE_MAP = {
    "PF": ["TAXI_OUT"], "Taxi Out": ["TAXI_OUT"], "Take Off": ["TAKEOFF"], "RTO": ["TAKEOFF"],
    "Initial CLB": ["INITIAL_CLIMB"], "Climb": ["CLIMB"], "Cruise": ["CRUISE"], "Descent": ["DESCENT"],
    "Approach": ["APPROACH"], "Go Around": ["GO_AROUND"], "Landing": ["LANDING"],
    "Taxi In": ["TAXI_IN"],
}
COND = re.compile(r"^\s*\[([^\]]+)\]\s*(<=|>=|<|>|=)\s*(-?[\d.]+)\s*$")
CATEGORY = [
    ("Bank", "Controlo de voo"), ("Roll", "Controlo de voo"), ("Pitch", "Controlo de voo"),
    ("Glideslope", "Aproximação"), ("Localizer", "Aproximação"), ("Approach", "Aproximação"),
    ("Landing", "Aterragem"), ("Touchdown", "Aterragem"), ("Flare", "Aterragem"),
    ("Takeoff", "Descolagem"), ("Rotation", "Descolagem"), ("Lift", "Descolagem"),
    ("Taxi", "Solo"), ("Ground", "Solo"), ("Speed", "Velocidade"), ("Mach", "Velocidade"),
    ("Flap", "Configuração"), ("Gear", "Configuração"), ("Slat", "Configuração"),
    ("GPWS", "Avisos"), ("TCAS", "Avisos"), ("Windshear", "Avisos"), ("Stall", "Avisos"),
    ("Thrust", "Motores"), ("N1", "Motores"), ("ITT", "Motores"), ("Engine", "Motores"),
    ("AP ", "Automatismos"), ("Autopilot", "Automatismos"), ("Altitude", "Altitude"),
    ("Acceleration", "Cargas"),
]

MITIG = {
    1: ["Registar em tendência mensal por aeroporto, procedimento e tipo de operação.",
        "Incluir o tema na próxima comunicação de Safety Promotion se a tendência subir."],
    2: ["Revisão pela equipa FDM com validação dos dados e contexto (meteorologia, ATC, NOTAM).",
        "Contacto confidencial à tripulação através do gatekeeper.",
        "Verificar conformidade com o SOP e propor reforço em briefing ou treino recorrente."],
    3: ["Comunicar ao Safety Manager em 24 h e abrir investigação no SMS.",
        "Avaliar obrigação de reporte MOR ao abrigo do Reg. (UE) 376/2014 (72 h).",
        "Avaliar inspeção de Manutenção quando aplicável (AMM) e treino adicional da tripulação."],
}


def _num(x):
    try:
        if x is None or (isinstance(x, float) and x != x):
            return None
        return float(str(x).strip())
    except ValueError:
        return None


def _cells(row):
    return [str(x).strip() for x in row if str(x) not in ("nan", "NaT", "None") and str(x).strip() != ""]


def _phase_rows(path: str) -> dict[int, list[str]]:
    """Fases selecionadas: células da linha 'PF' com preenchimento (cinzento no export do fornecedor)."""
    try:
        import openpyxl
        ws = openpyxl.load_workbook(path).active
    except Exception:
        return {}
    out = {}
    for row in ws.iter_rows():
        if row and any(c.value == "PF" for c in row):
            sel = []
            for c in row:
                if c.value in PHASE_MAP and c.fill is not None and c.fill.fill_type and \
                        str(c.fill.fgColor.rgb).upper() not in ("FFFFFFFF", "00000000"):
                    for ph in PHASE_MAP[c.value]:
                        if ph not in sel:
                            sel.append(ph)
            out[row[0].row - 1] = sel  # índice 0-based como no pandas
    return out


def parse(path: str) -> list[dict]:
    d = pd.read_excel(path, header=None)
    phase_rows = _phase_rows(path)
    rows = [_cells(d.iloc[i].tolist()) for i in range(len(d))]
    events, cur, mode = [], None, None
    for i, r in enumerate(rows):
        if not r:
            continue
        k = r[0]
        if i in phase_rows and cur is not None:
            cur["phases"] = phase_rows[i]
        if k == "Event:":
            cur = {"name": r[1] if len(r) > 1 else "", "levels": {}, "desc": "", "detection": "", "trigger": ""}
            events.append(cur)
            mode = None
        elif cur is None:
            continue
        elif k == "Event Code:":
            cur["code"] = r[1] if len(r) > 1 else ""
        elif k == "Event ID:":
            mode = None
        elif k == "Description:":
            mode = "desc"
        elif k == "Flight Phases":
            mode = None
        elif k == "Detection Period:":
            mode = "det"
        elif k.startswith("Trigger"):
            cur["trigger"] = r[1].strip("[] ") if len(r) > 1 else ""
            mode = None
        elif k in ("Low", "Med", "High"):
            op = r[1].strip()
            nums = [x for x in r[2:] if _num(x) is not None]
            th = _num(nums[0]) if len(nums) >= 1 else None
            du = _num(nums[1]) if len(nums) >= 2 else None
            cur["levels"][k] = (op, th, du)
        elif mode == "desc" and k not in ("PF",):
            cur["desc"] = (cur["desc"] + " " + " ".join(r)).strip()
        elif mode == "det":
            cur["detection"] = (cur["detection"] + " " + " ".join(r)).strip()
    return events


def to_yaml_events(raw: list[dict]) -> tuple[list[dict], dict]:
    out, report = [], {"auto": 0, "review": []}
    for e in raw:
        lv = e["levels"]
        ops = {v[0] for v in lv.values() if v[1] is not None}
        op = ops.pop() if len(ops) == 1 else ">"
        ths = [lv.get(n, (None, None, None))[1] for n in ("Low", "Med", "High")]
        dus = [lv.get(n, (None, None, None))[2] for n in ("Low", "Med", "High")]
        if all(t is None for t in ths) or not e["trigger"]:
            report["review"].append(f"{e.get('code','')} {e['name']}: sem limiares ou trigger")
            continue
        conds, unparsed = [], []
        det = re.sub(r"\s+", " ", e["detection"]).strip()
        if det:
            for part in re.split(r"\bAND\b", det):
                m = COND.match(part)
                if m:
                    conds.append({"param": m.group(1).strip(), "op": "==" if m.group(2) == "=" else m.group(2),
                                  "value": float(m.group(3))})
                else:
                    unparsed.append(part.strip())
        cat = next((c for key, c in CATEGORY if key.lower() in e["name"].lower()), "Operação")
        ev = {
            "id": e.get("code") or e["name"],
            "code": e.get("code", ""),
            "name": e["name"],
            "category": cat,
            "parameter": e["trigger"],
            "op": op,
            "mode": "min" if op == "<" else "max",
            "thresholds": ths,
            "durations": [d if d is not None else 0.0 for d in dus],
            "phases": e.get("phases", []),
            "conditions": conds,
            "detection": det,
            "description": e["desc"],
            "mitigation": MITIG,
        }
        if unparsed:
            ev["unparsed_conditions"] = unparsed
            report["review"].append(f"{ev['code']} {ev['name']}: condição com OR ou agrupamento, avaliada pelo motor de expressões: {det}")
        report["auto"] += 1
        out.append(ev)
    return out, report


def main(src: str, dst: str, aircraft: str) -> None:
    evs, rep = to_yaml_events(parse(src))
    header = (f"# Catálogo de eventos importado de {Path(src).name}\n"
              f"# Aeronave: {aircraft}\n"
              f"# Níveis: Low=1, Med=2, High=3; durações por nível em segundos.\n"
              f"# Nomes de parâmetros iguais aos do fornecedor: o frame_layout.yaml tem de usar os mesmos nomes.\n")
    cfg = {"aircraft": aircraft, "source": Path(src).name, "events": evs}
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(header + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print(f"{len(evs)} eventos importados; {len(rep['review'])} com condições compostas a confirmar")
    for r in rep["review"]:
        print("  -", r)


if __name__ == "__main__":
    main(*sys.argv[1:4])
