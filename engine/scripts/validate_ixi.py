"""Valida o motor contra os volumes publicados de voluntários do banco público IXI.

Uso: python validate_ixi.py PASTA_COM_T1 referencia.csv PASTA_DE_SAIDA

Roda a volumetria completa em cada `SUJEITO.nii.gz` da pasta e compara as
estruturas do relatório com a linha do mesmo sujeito na tabela do Neurodesk
(tests/data/brainquant_ixi_volumes.csv), a mesma que ajustou as normas. Se o
motor repete os passos das normas, as diferenças têm de ser pequenas e sem
desvio para um lado só.
"""
from __future__ import annotations

import csv
import shutil
import statistics
import sys
from pathlib import Path

from neurolaudo.volumetry.norms import load_norms
from neurolaudo.volumetry.pipeline import run_exam
from neurolaudo.volumetry.report import ReportHeader
from neurolaudo.volumetry.tables import read_volumes_csv

MEAN_LIMIT = 0.2      # % de desvio médio aceito por estrutura (a rodada de 16/11/2026 deu 0,00)
SINGLE_LIMIT = 1.0    # % de diferença aceita em um sujeito


def main(argv: list[str]) -> int:
    folder, reference_csv, out = Path(argv[1]), argv[2], Path(argv[3])
    out.mkdir(parents=True, exist_ok=True)
    with open(reference_csv, newline="", encoding="utf-8") as fh:
        people = {row["subject"]: row for row in csv.DictReader(fh)}
    norms = load_norms()
    names = [s.title for s in norms.structures] + ["Volume intracraniano"]
    diffs: dict[str, list[float]] = {name: [] for name in names}
    lines = []
    seconds = []

    for path in sorted(folder.glob("*.nii.gz")):
        subject = path.name[:-len(".nii.gz")]
        person = people.get(subject)
        if person is None or person.get("exclude"):
            print(f"{subject}: fora da tabela de referência, pulado")
            continue
        result = run_exam(str(path), str(out / subject), age=float(person["age"]), sex=person["sex"],
                          header=ReportHeader(patient_name=f"Voluntário público {subject[:6]}", series="T1 (banco público IXI)"),
                          progress=lambda fraction, message: None)
        seconds.append(result["tempos_s"]["total"])
        measured = read_volumes_csv(str(out / subject / "trabalho" / "volumes.csv"))
        published = read_volumes_csv(reference_csv, subject)
        row = []
        for structure in norms.structures:
            here = sum(measured[c] for c in structure.columns)
            there = sum(published[c] for c in structure.columns)
            row.append(100.0 * (here / there - 1.0))
        row.append(100.0 * (measured[norms.icv_column] / published[norms.icv_column] - 1.0))
        for name, value in zip(names, row):
            diffs[name].append(value)
        cut = result["recorte"]
        size = " x ".join(str(b - a) for a, b in zip(cut["inicio"], cut["fim"]))
        lines.append(f"{subject:22s} {person['sex']:6s} {float(person['age']):5.1f} anos  maior diferença {max(abs(v) for v in row):5.2f}%  "
                     f"recorte {size} voxels, {cut['segmentacoes']} segmentação(ões)  {result['tempos_s']['total']:.0f} s")
        print(lines[-1], flush=True)
        if len(seconds) == 1:   # páginas do primeiro sujeito, para olhar
            for name in ("relatorio.png", "conferencia.png", "relatorio.pdf", "resultado.json"):
                shutil.copy(out / subject / name, out / name)

    if not seconds:
        print("Nenhum sujeito da tabela de referência na pasta.")
        return 1
    report = [f"Validação do motor de volumetria em {len(seconds)} voluntários do banco público IXI.",
              "Diferença, em %, entre o volume medido aqui e o publicado pelo Neurodesk para o mesmo exame.", "",
              *lines, "", f"{'estrutura':30s} {'média':>8s} {'desvio':>8s} {'maior':>8s}"]
    failed = False
    for name in names:
        values = diffs[name]
        mean = statistics.fmean(values)
        spread = statistics.stdev(values) if len(values) > 1 else 0.0
        worst = max(abs(v) for v in values)
        failed = failed or abs(mean) > MEAN_LIMIT or worst > SINGLE_LIMIT
        report.append(f"{name:30s} {mean:+8.2f} {spread:8.2f} {worst:8.2f}")
    report += ["", f"Tempo médio por exame: {statistics.fmean(seconds):.0f} s.",
               f"Limites: média até {MEAN_LIMIT:.1f}% e cada sujeito até {SINGLE_LIMIT:.1f}%. "
               + ("ALGUM LIMITE FOI PASSADO." if failed else "Dentro dos limites.")]
    text = "\n".join(report)
    print("\n" + text)
    (out / "validacao.txt").write_text(text + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
