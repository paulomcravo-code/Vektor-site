"""
Gera um ficheiro .dat ARINC 717 sintético (voo completo ~45 min) a partir do
frame_layout de exemplo, com algumas excedências injetadas para testar a
plataforma ponta a ponta. Uso:
    python tools/gerar_dat_teste.py profiles/atr72_exemplo saida.dat [--limpo]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fdm.decoder import SYNC_WORDS, FrameLayout  # noqa: E402


def profile(seed: int = 7, clean: bool = False):
    rng = np.random.default_rng(seed)
    T = 2700
    t = np.arange(T, dtype=float)
    alt = np.full(T, 150.0); ias = np.zeros(T); gs = np.zeros(T)
    air = np.zeros(T); gear = np.ones(T); flap = np.zeros(T)
    pitch = np.zeros(T); roll = np.zeros(T); tq = np.full(T, 20.0); gsdev = np.zeros(T)

    # Taxi 0-300 s (com troço rápido), corrida 300-335, liftoff 335
    gs[30:290] = 15 + 3 * np.sin(t[30:290] / 20)
    if not clean:
        gs[180:200] = 32
    flap[:600] = 15
    roll_idx = slice(300, 336)
    ias[roll_idx] = np.linspace(40, 115, 36); gs[roll_idx] = ias[roll_idx]; tq[300:900] = 95
    lo = 336
    # Subida até FL170 em ~15 min
    climb = np.arange(lo, 1250)
    alt[climb] = 150 + (17000 - 150) * (1 - np.exp(-(climb - lo) / 330)) / (1 - np.exp(-914 / 330))
    ias[climb] = np.clip(120 + (climb - lo) * 0.3, 0, 200)
    pitch[climb] = 7 * np.exp(-(climb - lo) / 200) + 2
    pitch[lo - 4:lo + 3] = np.linspace(4, 11.6 if not clean else 8.5, 7)
    air[lo:] = 1
    gear[lo + 8:] = 0
    # Cruzeiro
    cr = np.arange(1250, 1750)
    alt[cr] = 17000; ias[cr] = 205; pitch[cr] = 1.5; tq[900:1750] = 75
    # Descida
    ds = np.arange(1750, 2400)
    alt[ds] = np.linspace(17000, 1800, len(ds)); ias[ds] = 230; pitch[ds] = -2.5; tq[1750:2400] = 30
    if not clean:
        ias[1900:1925] = 252  # VMO
        ias[2150:2200] = 268  # >250 kt abaixo de FL100
        roll[1800:1806] = 41  # pranchamento
    else:
        ias[2150:2200] = 240
    # Aproximação final
    ap = np.arange(2400, 2580)
    alt[ap] = np.linspace(1800, 150, len(ap)); ias[ap] = np.linspace(170, 112, len(ap))
    pitch[ap] = 0.5; flap[2400:] = 30; tq[2400:2580] = 35
    gear[2440:] = 1
    if not clean:
        alt[2490:2510] = alt[2490] - np.cumsum(np.full(20, 22.0))  # ~1300 fpm abaixo de 1000 ft
        alt[2510:2580] = np.linspace(alt[2509], 150, 70)
        gsdev[2495:2515] = 1.7
    td = 2580
    air[td:] = 0
    alt[td:] = 150
    ias[td:] = np.clip(112 - (t[td:] - td) * 3.0, 0, None)
    gs[2400:td] = ias[2400:td] - 5; gs[td:] = ias[td:]
    gs[td + 60:] = 14
    roll += rng.normal(0, 1.2, T) * air
    ias += rng.normal(0, 0.4, T) * (ias > 0)
    ralt = np.clip(alt - 150, 0, 2500)
    ralt[air == 0] = 0
    if not clean:
        roll[td - 6:td - 2] = 12
    return dict(T=T, ALT_STD=alt, IAS=np.clip(ias, 0, None), RALT=ralt, PITCH=pitch, ROLL=roll,
                HEADING=(90 + 0.02 * t) % 360, AIR_GND=air, FLAP=flap, GEAR=gear, TQ1=tq,
                GS=np.clip(gs, 0, None), GSDEV=gsdev, touchdown=td, clean=clean)


def encode(v: float, p) -> int:
    msb, lsb = p.bits
    n = msb - lsb + 1
    raw = int(round((v - p.offset) / p.scale)) if p.encoding != "discrete" else int(round(v))
    if p.encoding == "bnr":
        raw = max(-(1 << (n - 1)), min((1 << (n - 1)) - 1, raw)) & ((1 << n) - 1)
    else:
        raw = max(0, min((1 << n) - 1, raw))
    return raw << (lsb - 1)


def build(profile_dir: str, out: str, clean: bool = False):
    lay = FrameLayout.load(Path(profile_dir) / "frame_layout.yaml")
    prof = profile(clean=clean)
    T, wps = prof["T"], lay.words_per_second
    rng = np.random.default_rng(3)
    words = rng.integers(0, 4096, size=T * wps).astype(np.uint16)  # palavras não mapeadas
    tds = prof["touchdown"]
    for s in range(T):
        sf = s % 4 + 1
        words[s * wps] = SYNC_WORDS[sf - 1]
        for name, p in lay.params.items():
            for (lsf, w) in p.locations:
                if lsf != sf:
                    continue
                tt = s + (w - 1) / wps
                if name == "VRTG":
                    val = 1.0 + 0.04 * np.sin(tt * 3)
                    if prof["AIR_GND"][s]:
                        val += rng.normal(0, 0.05)
                    if abs(tt - tds) < 0.6:
                        val = (1.86 if not prof["clean"] else 1.35) - 0.8 * abs(tt - tds)
                else:
                    arr = prof[name]
                    i = min(int(tt), T - 2)
                    val = arr[i] + (arr[i + 1] - arr[i]) * (tt - i) if p.encoding != "discrete" else arr[s]
                words[s * wps + w - 1] = encode(val, p)
    Path(out).write_bytes(words.astype("<u2").tobytes())
    return out


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], clean="--limpo" in sys.argv)
    print("Gerado:", sys.argv[2])
