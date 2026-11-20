"""Análise em linha de comando (processamento em lote de downloads):
    python cli.py <ficheiro.dat|.tsc> <perfil> <pasta_saida> [matricula]

Um download pode conter vários voos: é gerado um relatório PDF por voo.
"""
import sys
from pathlib import Path

from fdm.pipeline import analyse_download
from fdm.report import build_pdf

if __name__ == "__main__":
    f, prof, out = sys.argv[1:4]
    meta = {"registration": sys.argv[4]} if len(sys.argv) > 4 else {}
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    flights = analyse_download(open(f, "rb").read(), prof, meta)
    print(f"{len(flights)} voo(s) no ficheiro")
    for fa in flights:
        m = fa.meta
        name = f"{m.get('registration', 'ACFT')}_voo{m['flight_index']}_{m.get('origin', '')}-{m.get('destination', '')}.pdf"
        (outdir / name).write_bytes(build_pdf(fa))
        print(f"  voo {m['flight_index']}: {m.get('origin')} -> {m.get('destination')} · {len(fa.events)} eventos · "
              f"risco máximo nível {fa.risk['max_level']} · {outdir / name}")
