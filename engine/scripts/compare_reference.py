"""Compara os volumes medidos aqui com os publicados para o mesmo voluntário público.

Uso: python compare_reference.py volumes.csv referencia.csv SUJEITO [tolerância em %]

A referência é a tabela do Neurodesk usada para ajustar as normas
(tests/data/brainquant_ixi_volumes.csv). Se o motor repete os mesmos passos, os
volumes do mesmo exame têm de sair praticamente iguais.
"""
from __future__ import annotations

import sys

from neurolaudo.volumetry.norms import load_norms
from neurolaudo.volumetry.tables import read_volumes_csv


def main(argv: list[str]) -> int:
    measured = read_volumes_csv(argv[1])
    reference = read_volumes_csv(argv[2], argv[3])
    tolerance = float(argv[4]) if len(argv) > 4 else 2.0
    norms = load_norms()

    print(f"{'coluna':38s} {'aqui (mL)':>10s} {'publicado':>10s} {'diferença':>10s}")
    shared = [c for c in reference if c in measured and reference[c] > 0 and c != "age"]
    for column in sorted(shared, key=lambda c: -abs(measured[c] / reference[c] - 1.0)):
        diff = 100.0 * (measured[column] / reference[column] - 1.0)
        print(f"{column:38s} {measured[column] / 1000:10.2f} {reference[column] / 1000:10.2f} {diff:+9.2f}%")

    worst = 0.0
    print("\nEstruturas do relatório:")
    for structure in norms.structures:
        here = sum(measured[c] for c in structure.columns)
        published = sum(reference[c] for c in structure.columns)
        diff = 100.0 * (here / published - 1.0)
        worst = max(worst, abs(diff))
        print(f"  {structure.title:30s} {here / 1000:9.2f} {published / 1000:9.2f} {diff:+8.2f}%")
    icv = 100.0 * (measured[norms.icv_column] / reference[norms.icv_column] - 1.0)
    worst = max(worst, abs(icv))
    print(f"  {'Volume intracraniano':30s} {measured[norms.icv_column] / 1000:9.2f} "
          f"{reference[norms.icv_column] / 1000:9.2f} {icv:+8.2f}%")
    print(f"\nMaior diferença nas estruturas do relatório: {worst:.2f}% (tolerância {tolerance:.1f}%).")
    return 0 if worst <= tolerance else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
