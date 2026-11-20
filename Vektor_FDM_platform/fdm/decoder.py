"""
Descodificador ARINC 717 (QAR / DFDR) para ficheiros .dat brutos.

Princípio: um ficheiro .dat de QAR é uma sequência de palavras de 12 bits
organizadas em subframes de 1 segundo (64/128/256/512/1024 palavras por
segundo). Cada subframe começa com uma palavra de sincronismo (sync word).
Quatro subframes formam um superframe/frame de 4 segundos.
A localização de cada parâmetro (subframe, palavra, bits) e a sua conversão
para unidades de engenharia vêm do LFL / Data Frame Layout do fabricante,
que aqui é descrito num ficheiro YAML (profiles/<perfil>/frame_layout.yaml).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import re

import numpy as np
import pandas as pd
import yaml

SYNC_WORDS = (0x247, 0x5B8, 0xA47, 0xDB8)


@dataclass
class ParamDef:
    name: str
    description: str
    units: str
    encoding: str  # bnr (complemento para 2), unsigned, discrete
    bits: tuple[int, int]  # (msb, lsb) numerados 12..1
    locations: list[tuple[int, int]]  # [(subframe 1..4, palavra 1..wps)]
    scale: float = 1.0
    offset: float = 0.0
    discrete_map: dict | None = None
    fine_offset: int | None = None  # palavra de resolução fina (ex.: lat/lon em 2 palavras)
    fine_bits: int = 12
    invalid_above: float | None = None  # valores acima disto são marcados como inválidos (NaN)
    columns: list[str] | None = None  # storage csv: nomes possíveis da coluna no ficheiro

    @property
    def rate_hz(self) -> float:
        return len(self.locations) / 4.0 if self.locations else 1.0


@dataclass
class FrameLayout:
    aircraft_type: str
    words_per_second: int
    storage: str  # "word16" | "packed12" (MSB) | "packed12_lsb" (LSB, MQAR) | "csv" (unidades de engenharia)
    byte_order: str
    params: dict[str, ParamDef] = field(default_factory=dict)
    derived: dict = field(default_factory=dict)
    notes: str = ""
    validated: bool = False
    time_column: str | None = None  # storage csv

    @classmethod
    def load(cls, path: str | Path) -> "FrameLayout":
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        fl = cls(
            aircraft_type=cfg["aircraft_type"],
            words_per_second=int(cfg.get("words_per_second", 0)),
            storage=cfg.get("storage", "word16"),
            byte_order=cfg.get("byte_order", "little"),
        )
        for name, p in cfg["parameters"].items():
            locs = []
            for loc in p.get("locations", []):
                sfs = [1, 2, 3, 4] if loc.get("subframe", "all") == "all" else [int(loc["subframe"])]
                words = loc["word"] if isinstance(loc["word"], list) else [loc["word"]]
                for sf in sfs:
                    for w in words:
                        locs.append((sf, int(w)))
            fl.params[name] = ParamDef(
                name=name,
                description=p.get("description", name),
                units=p.get("units", ""),
                encoding=p.get("encoding", "bnr"),
                bits=tuple(p.get("bits", [12, 1])),
                locations=sorted(locs),
                scale=float(p.get("scale", 1.0)),
                offset=float(p.get("offset", 0.0)),
                discrete_map=p.get("discrete_map"),
                fine_offset=p.get("fine_offset"),
                fine_bits=int(p.get("fine_bits", 12)),
                invalid_above=p.get("invalid_above"),
                columns=p.get("columns"),
            )
        fl.derived = cfg.get("derived", {}) or {}
        fl.notes = cfg.get("notes", "")
        fl.validated = bool(cfg.get("validated", False))
        fl.time_column = cfg.get("time_column")
        return fl


@dataclass
class DecodeResult:
    data: dict[str, pd.Series]  # série temporal por parâmetro (índice = segundos)
    layout: FrameLayout
    n_frames: int
    sync_losses: int
    duration_s: float
    quality_pct: float  # % de subframes com sincronismo válido


def _read_words(raw: bytes, layout: FrameLayout) -> np.ndarray:
    if layout.storage == "word16":
        dt = "<u2" if layout.byte_order == "little" else ">u2"
        words = np.frombuffer(raw[: len(raw) // 2 * 2], dtype=dt)
        return (words & 0x0FFF).astype(np.int32)
    if layout.storage == "packed12_lsb":
        # Fluxo contínuo de bits, bit menos significativo primeiro (ex.: MQAR L3/Teledyne .tsc).
        # O cabeçalho ASCII não tem múltiplo de 12 bits: procura-se o deslocamento em bits do
        # primeiro sincronismo válido e convertem-se as palavras por blocos (memória baixa).
        b = np.frombuffer(raw, dtype=np.uint8)
        off = _bit_offset_lsb(b, layout.words_per_second)
        return _lsb_words(b, off)
    if layout.storage == "packed12":
        b = np.frombuffer(raw, dtype=np.uint8)
        bits = np.unpackbits(b)  # MSB primeiro
        n = len(bits) // 12
        bits = bits[: n * 12].reshape(n, 12)
        weights = 1 << np.arange(11, -1, -1)
        return (bits * weights).sum(axis=1).astype(np.int32)
    raise ValueError(f"Formato de armazenamento desconhecido: {layout.storage}")


def _lsb_words(b: np.ndarray, bit_off: int, chunk_words: int = 1_000_000) -> np.ndarray:
    """Palavras de 12 bits de um fluxo LSB primeiro, a partir de bit_off, em blocos."""
    total_bits = len(b) * 8 - bit_off
    n = total_bits // 12
    out = np.empty(n, dtype=np.int32)
    w = 1 << np.arange(12, dtype=np.uint16)
    done = 0
    while done < n:
        k = min(chunk_words, n - done)
        start_bit = bit_off + done * 12
        b0 = start_bit // 8
        nbytes = (start_bit % 8 + k * 12 + 7) // 8
        bits = np.unpackbits(b[b0:b0 + nbytes], bitorder="little")[start_bit % 8: start_bit % 8 + k * 12]
        out[done:done + k] = (bits.reshape(k, 12).astype(np.uint16) * w).sum(axis=1, dtype=np.uint32)
        done += k
    return out


def _bit_offset_lsb(b: np.ndarray, wps: int, search_bytes: int = 65536) -> int:
    """Deslocamento (em bits) do primeiro sync seguido de dois syncs 1 s e 2 s depois."""
    L = wps * 12
    nb = min(len(b), search_bytes + 3 * L // 8 + 8)
    bits = np.unpackbits(b[:nb], bitorder="little").astype(np.uint16)
    m = len(bits) - 12
    v = np.zeros(m, dtype=np.uint16)
    for k in range(12):
        v |= bits[k:k + m] << k
    cand = np.where(np.isin(v[: m - 2 * L], SYNC_WORDS))[0]
    for c in cand:
        k = SYNC_WORDS.index(int(v[c]))
        if v[c + L] == SYNC_WORDS[(k + 1) % 4] and v[c + 2 * L] == SYNC_WORDS[(k + 2) % 4]:
            return int(c)
    raise ValueError("Sem sincronismo ARINC 717 no fluxo LSB: verifique words_per_second.")


def _find_sync(words: np.ndarray, start: int, wps: int) -> int | None:
    """Procura posição onde 3 subframes seguidos têm sync words na sequência correta."""
    for i in range(start, len(words) - 3 * wps):
        w = words[i]
        if w in SYNC_WORDS:
            k = SYNC_WORDS.index(w)
            if (words[i + wps] == SYNC_WORDS[(k + 1) % 4]
                    and words[i + 2 * wps] == SYNC_WORDS[(k + 2) % 4]):
                return i
    return None


def _extract(raw_vals: np.ndarray, p: ParamDef, fine_vals: np.ndarray | None = None) -> np.ndarray:
    msb, lsb = p.bits
    nbits = msb - lsb + 1
    v = (raw_vals >> (lsb - 1)) & ((1 << nbits) - 1)
    if p.encoding == "bnr":
        sign = 1 << (nbits - 1)
        v = np.where(v & sign, v - (1 << nbits), v)
    v = v.astype(float)
    if fine_vals is not None:
        v = v + (fine_vals & ((1 << p.fine_bits) - 1)) / float(1 << p.fine_bits)
    out = v * p.scale + p.offset
    if p.invalid_above is not None:
        out = np.where(out > float(p.invalid_above), np.nan, out)
    return out


def _norm(c: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(c).lower())


def _time_seconds(col: pd.Series) -> np.ndarray:
    """Tempo em segundos a partir de segundos, HH:MM:SS(.s) ou data/hora; corrige a passagem da meia-noite."""
    num = pd.to_numeric(col, errors="coerce")
    if num.notna().mean() > 0.9:
        return num.to_numpy(dtype=float)
    td = pd.to_timedelta(col.astype(str).str.strip(), errors="coerce")
    if td.notna().mean() > 0.9:
        t = td.dt.total_seconds().to_numpy()
    else:
        dt = pd.to_datetime(col, errors="coerce")
        t = (dt - dt.dropna().iloc[0]).dt.total_seconds().to_numpy()
    jumps = np.where(np.diff(t) < -43200)[0]
    for j in jumps:
        t[j + 1:] += 86400
    return t


def decode_csv(raw: bytes, layout: FrameLayout) -> DecodeResult:
    """Ficheiro já em unidades de engenharia (exportação CSV do software do fornecedor ou do fabricante).

    Cada parâmetro do frame_layout procura a sua coluna pelo nome do parâmetro ou pelos nomes em `columns`,
    ignorando maiúsculas, espaços e unidades. Linhas com várias amostras por segundo são mantidas."""
    import io
    txt = raw.decode("utf-8-sig", errors="replace")
    sep = ";" if txt[:2000].count(";") > txt[:2000].count(",") else ","
    df = pd.read_csv(io.StringIO(txt), sep=sep, low_memory=False)
    cols = {_norm(c): c for c in df.columns}
    tcol = None
    for cand in [layout.time_column, "Time", "Time (s)", "Seconds", "UTC Time", "GMT", "Timestamp", "Relative Time"]:
        if cand and _norm(cand) in cols:
            tcol = cols[_norm(cand)]
            break
    tcol = tcol or df.columns[0]
    t = _time_seconds(df[tcol])
    data: dict[str, pd.Series] = {}
    for name, p in layout.params.items():
        for cand in [name, *(p.columns or [])]:
            c = cols.get(_norm(cand))
            if c is None:
                c = next((orig for k, orig in cols.items() if k.startswith(_norm(cand))), None)
            if c is not None:
                v = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float) * p.scale + p.offset
                ok = ~np.isnan(t)
                s = pd.Series(v[ok], index=t[ok], name=name)
                data[name] = s[~s.index.duplicated(keep="first")].sort_index()
                break
    if not data:
        raise ValueError("Nenhuma coluna do CSV corresponde aos parâmetros do perfil.")
    dur = float(np.nanmax(t) - np.nanmin(t)) if len(t) else 0.0
    return DecodeResult(data=data, layout=layout, n_frames=len(df), sync_losses=0, duration_s=dur, quality_pct=100.0)


def decode(path_or_bytes, layout: FrameLayout) -> DecodeResult:
    raw = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    if layout.storage == "csv":
        return decode_csv(bytes(raw), layout)
    if bytes(raw[:40]).startswith(b"// L3 Communications") and b"\xef\xbe" in bytes(raw[:600]):
        raise ValueError("Ficheiro L3 FA2100 (.fdr) comprimido em formato proprietário. Exporte os dados expandidos "
                         "(ARINC 717 sem compressão ou CSV em unidades de engenharia) no software L3 ou do fornecedor FDM.")
    words = _read_words(bytes(raw), layout)
    wps = layout.words_per_second

    pos = _find_sync(words, 0, wps)
    if pos is None:
        raise ValueError("Sem sincronismo ARINC 717: verifique words_per_second e storage no frame_layout.")

    # Alinhar ao início do subframe 1
    k = SYNC_WORDS.index(words[pos])
    pos += ((4 - k) % 4) * wps

    subframes: list[tuple[int, int]] = []  # (índice da palavra, nº do subframe 1..4)
    sync_losses, bad = 0, 0
    sec = 0
    seconds: list[int] = []
    while pos + wps <= len(words):
        w = words[pos]
        if w in SYNC_WORDS:
            subframes.append((pos, SYNC_WORDS.index(w) + 1))
            seconds.append(sec)
            pos += wps
            sec += 1
        else:
            sync_losses += 1
            bad += 1
            nxt = _find_sync(words, pos + 1, wps)
            if nxt is None:
                break
            gap = max(1, round((nxt - pos) / wps))
            sec += gap
            pos = nxt

    idx = np.array([s[0] for s in subframes])
    sfn = np.array([s[1] for s in subframes])
    t_sub = np.array(seconds, dtype=float)

    data: dict[str, pd.Series] = {}
    for name, p in layout.params.items():
        times, vals = [], []
        per_sf: dict[int, list[int]] = {}
        for sf, wd in p.locations:
            per_sf.setdefault(sf, []).append(wd)
        for sf, wlist in per_sf.items():
            mask = sfn == sf
            base = idx[mask]
            t0 = t_sub[mask]
            for j, wd in enumerate(sorted(wlist)):
                ii = base + (wd - 1)
                ok = ii < len(words) - (p.fine_offset or 0)
                fine = words[ii[ok] + p.fine_offset] if p.fine_offset else None
                vals.append(_extract(words[ii[ok]], p, fine))
                times.append(t0[ok] + (wd - 1) / wps)
        if not vals:
            continue
        t = np.concatenate(times)
        v = np.concatenate(vals)
        order = np.argsort(t)
        s = pd.Series(v[order], index=np.round(t[order], 3), name=name)
        data[name] = s[~s.index.duplicated()]

    total = len(subframes) + bad
    return DecodeResult(
        data=data,
        layout=layout,
        n_frames=len(subframes) // 4,
        sync_losses=sync_losses,
        duration_s=float(t_sub[-1] + 1) if len(t_sub) else 0.0,
        quality_pct=100.0 * len(subframes) / total if total else 0.0,
    )


def to_dataframe(res: DecodeResult, hz: float = 1.0) -> pd.DataFrame:
    """Reamostra todos os parâmetros para uma grelha comum (por omissão 1 Hz)."""
    grid = np.arange(0, res.duration_s, 1.0 / hz)
    out = pd.DataFrame(index=grid)
    for name, s in res.data.items():
        p = res.layout.params[name]
        if p.encoding == "discrete":
            out[name] = s.reindex(grid, method="ffill")
        else:
            t, v = s.index.values, s.values
            good = ~np.isnan(v)
            if not good.any():
                out[name] = np.nan
                continue
            y = np.interp(grid, t[good], v[good])
            # manter inválido onde a amostra mais próxima é inválida
            near = np.clip(np.searchsorted(t, grid), 0, len(t) - 1)
            y[np.isnan(v[near])] = np.nan
            out[name] = y
    out.index.name = "t_s"
    return out
