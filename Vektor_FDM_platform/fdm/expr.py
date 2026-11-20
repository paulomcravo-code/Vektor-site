"""
Avaliador de expressões no estilo dos conjuntos de eventos dos fornecedores FDM.

Exemplos aceites:
    [Radio Height] < 1000 AND [Radio Height] > 100
    [Height Above Airfield] > 1000 OR ([Height Above Airfield] <= 0 AND [AIR GROUND] < 0.5)
    ([N1 Engine 1] + [N1 Engine 2]) / 2
    [Vertical Speed(-90)] < -1000        (valor de 90 s antes)
    [Computed Airspeed (30)]             (valor de 30 s depois)

Os parâmetros são lidos de um DataFrame a 1 Hz. Só se permitem nomes de parâmetros,
números, operadores aritméticos e de comparação, AND/OR/NOT, parênteses e abs().
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

REF = re.compile(r"\[([^\]\(]+?)\s*(?:\(\s*(-?\d+(?:\.\d+)?)\s*\))?\s*\]")
ALLOWED = re.compile(r"^[\sv\d_.+\-*/()<>=!&|~a-z]*$")


class MissingParams(Exception):
    def __init__(self, names):
        super().__init__(", ".join(names))
        self.names = list(names)


def refs(expr: str) -> list[tuple[str, float]]:
    return [(m.group(1).strip(), float(m.group(2) or 0)) for m in REF.finditer(expr or "")]


def evaluate(expr: str, df: pd.DataFrame, extra: dict | None = None) -> np.ndarray:
    extra = extra or {}
    names, local = {}, {}

    def sub(m):
        name, shift = m.group(1).strip(), float(m.group(2) or 0)
        key = (name, shift)
        if key not in names:
            names[key] = f"v{len(names)}"
        return names[key]

    py = REF.sub(sub, expr)
    missing = sorted({n for n, _ in names if n not in df.columns and n not in extra})
    if missing:
        raise MissingParams(missing)
    for (name, shift), var in names.items():
        s = df[name] if name in df.columns else extra[name]
        s = pd.Series(np.asarray(s, dtype=float), index=df.index)
        if shift:
            s = s.shift(int(round(-shift)))
        local[var] = s
    py = re.sub(r"\bAND\b", " and ", py, flags=re.I)
    py = re.sub(r"\bOR\b", " or ", py, flags=re.I)
    py = re.sub(r"\bNOT\b", " not ", py, flags=re.I)
    py = re.sub(r"(?<![<>=!])=(?!=)", "==", py)
    check = re.sub(r"\b(and|or|not|abs)\b", "", py)
    if not ALLOWED.match(check):
        raise ValueError(f"Expressão não suportada: {expr}")
    if not local:
        return np.full(len(df), float(eval(py, {"__builtins__": {}}, {})))  # noqa: S307 (só números)
    out = pd.eval(py, local_dict=local, engine="python", parser="pandas")
    return np.asarray(out)
