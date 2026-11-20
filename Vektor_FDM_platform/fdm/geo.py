"""Dados geográficos offline: aeroportos (OurAirports) e linha de costa (Natural Earth 1:50m).

Ambos os conjuntos são de domínio público e vêm embalados em assets/geo, para que
a plataforma funcione sem acesso à internet.
"""
from __future__ import annotations

import csv
import json
import math
from functools import lru_cache
from pathlib import Path

GEO = Path(__file__).resolve().parents[1] / "assets" / "geo"


@lru_cache(maxsize=1)
def airports() -> list[dict]:
    with open(GEO / "airports.csv", encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
            r["elev_ft"] = float(r["elev_ft"]) if r["elev_ft"] else None
            out.append(r)
        return out


def distance_nm(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 3440.065 * math.asin(math.sqrt(a))


def nearest_airport(lat: float, lon: float, max_nm: float = 15.0) -> dict | None:
    if lat is None or lon is None or lat != lat or lon != lon:
        return None
    best, bd = None, max_nm
    for a in airports():
        if abs(a["lat"] - lat) > 1 or abs(a["lon"] - lon) > 1.5:
            continue
        d = distance_nm(lat, lon, a["lat"], a["lon"])
        if d < bd:
            best, bd = a, d
    if best:
        best = dict(best, dist_nm=round(bd, 1))
    return best


@lru_cache(maxsize=1)
def land_polygons() -> list[list[list[float]]]:
    return json.loads((GEO / "land_50m.json").read_text())
