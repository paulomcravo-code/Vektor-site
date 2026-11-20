"""Deteção de fases de voo a partir dos parâmetros reamostrados a 1 Hz."""
from __future__ import annotations

import numpy as np
import pandas as pd

PHASES = ["GROUND", "TAXI_OUT", "TAKEOFF", "INITIAL_CLIMB", "CLIMB", "CRUISE", "DESCENT", "APPROACH", "LANDING"]
PHASE_PT = {
    "GROUND": "Solo / Taxi", "TAXI_OUT": "Táxi de saída", "TAXI_IN": "Táxi de chegada", "TAKEOFF": "Descolagem", "INITIAL_CLIMB": "Subida inicial",
    "CLIMB": "Subida", "CRUISE": "Cruzeiro", "DESCENT": "Descida",
    "APPROACH": "Aproximação", "LANDING": "Aterragem",
}
PHASES.append("TAXI_IN")


def air_mask(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Verdadeiro quando a aeronave está no ar.

    Ordem de preferência: discreto ar/solo (air_ground = 1 no ar, ou ground_flag = 1 no solo),
    depois altitude-rádio e velocidade, por fim só altitude-pressão relativa ao mínimo.
    """
    m = cfg.get("mapping", {})
    if m.get("air_ground") in df:
        return df[m["air_ground"]].fillna(0) > 0.5
    if m.get("ground_flag") in df:
        return ~(df[m["ground_flag"]].fillna(1) > 0.5)
    alt = df[m.get("altitude", "ALT_STD")]
    spd = None
    for k in ("airspeed", "groundspeed"):
        if m.get(k) in df:
            spd = df[m[k]]
            break
    if m.get("radio_altitude") in df:
        ra = df[m["radio_altitude"]]
        air = (ra > 20) | ra.isna()
        return air & (spd > 60) if spd is not None else air
    rel = alt - alt.rolling(3600, center=True, min_periods=1).min()
    return (rel > 300) & ((spd > 60) if spd is not None else True)


def detect_phases(df: pd.DataFrame, cfg: dict) -> tuple[pd.Series, dict]:
    """
    Usa o discreto ar/solo (ou RALT/IAS como alternativa), a altitude-rádio e a
    razão vertical derivada da altitude-pressão. Devolve a fase por segundo e
    marcos principais (descolagem, aterragem).
    """
    m = cfg.get("mapping", {})
    alt = df[m.get("altitude", "ALT_STD")]
    ralt = df[m.get("radio_altitude", "RALT")] if m.get("radio_altitude", "RALT") in df else alt - alt.min()
    ralt = ralt.fillna(5000)  # fora de alcance (acima de ~2500 ft) conta como alto
    air = air_mask(df, cfg)
    ias = df[m["airspeed"]] if m.get("airspeed") in df else (
        df[m["groundspeed"]] if m.get("groundspeed") in df else pd.Series(np.nan, index=df.index))

    vs = alt.diff().rolling(10, center=True, min_periods=1).mean() * 60.0  # ft/min
    df["VS_FPM"] = vs

    phase = pd.Series("GROUND", index=df.index, dtype=object)
    air_idx = np.where(air.values)[0]
    marks: dict = {}
    if len(air_idx):
        t_lo, t_td = df.index[air_idx[0]], df.index[air_idx[-1]]
        marks["liftoff_s"], marks["touchdown_s"] = float(t_lo), float(t_td)
        # Corrida de descolagem: recua desde o liftoff enquanto a IAS/GS > 30 kt
        spd = df[m["groundspeed"]] if m.get("groundspeed") in df else ias
        fast = np.fmax(ias.values, spd.values) > 30
        i0 = air_idx[0]
        while i0 > 0 and fast[i0 - 1]:
            i0 -= 1
        phase.iloc[i0:air_idx[0]] = "TAKEOFF"
        cruise_alt = alt[air].quantile(0.95)
        airborne = air.values
        climb = airborne & (vs > 300)
        desc = airborne & (vs < -300)
        level = airborne & ~climb & ~desc
        high = alt.values > max(10000.0, 0.5 * float(cruise_alt))
        cruise = level & high
        phase[airborne] = "CLIMB"
        phase[desc] = "DESCENT"
        phase[cruise] = "CRUISE"
        # patamares abaixo do nível de cruzeiro: subida antes do primeiro cruzeiro, descida depois do último
        if cruise.any():
            first_cr, last_cr = np.where(cruise)[0][[0, -1]]
            idx_all = np.arange(len(df))
            phase[level & ~high & (idx_all > last_cr)] = "DESCENT"
        t = df.index.values
        phase[airborne & (ralt < 1500) & (t < t_lo + 600)] = "INITIAL_CLIMB"
        top_desc = t[np.where(cruise)[0][-1]] if cruise.any() else t_lo
        phase[airborne & (ralt < 2500) & (t > top_desc)] = "APPROACH"
        # Aterragem: do flare (10 s antes do toque) até a velocidade cair abaixo de 30 kt
        slow = np.where((t > t_td) & ~fast)[0]
        t_end = t[slow[0]] if len(slow) else t[-1]
        marks["rollout_end_s"] = float(t_end)
        phase[(t >= t_td - 10) & (t <= t_end)] = "LANDING"
        phase[t > t_end] = "TAXI_IN"
        phase[(t < t[i0]) & (phase == "GROUND").values] = "TAXI_OUT"
    return phase, marks
