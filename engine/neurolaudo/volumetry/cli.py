"""Linha de comando da volumetria.

Por enquanto parte de uma tabela de volumes já medida (o CSV que o
`mri_synthseg --vol` grava) e produz o relatório:

    python -m neurolaudo.volumetry.cli relatorio --csv volumes.csv --idade 72 --sexo F --saida pasta

A segmentação em si (FreeSurfer) entra em `engine.py`, a ser testada em um Mac.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from neurolaudo.volumetry.norms import Assessment, assess, load_norms
from neurolaudo.volumetry.report import DISCLAIMER, ReportHeader, flag_text, percentile_text, save_pdf, save_png


def read_volumes_csv(path: str, row: str | None = None) -> dict[str, float]:
    """Lê uma linha do CSV de volumes (mm³). `row`: número da linha de dados (0 = primeira) ou o nome do sujeito."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("o CSV de volumes está vazio")
    first_column = next(iter(rows[0]))
    if row is None:
        chosen = rows[0]
    elif row.isdigit():
        index = int(row)
        if index >= len(rows):
            raise ValueError(f"o CSV tem {len(rows)} linha(s) de dados; não existe a linha {index}")
        chosen = rows[index]
    else:
        matches = [r for r in rows if r[first_column] == row]
        if not matches:
            raise ValueError(f"não há linha com '{row}' na coluna '{first_column}'")
        chosen = matches[0]
    volumes: dict[str, float] = {}
    for key, value in chosen.items():
        try:
            volumes[key.strip()] = float(value)
        except (TypeError, ValueError):
            continue
    return volumes


def result_json(assessment: Assessment) -> dict:
    """O resultado em forma de dados, para o complemento do IsiX mostrar."""
    return {
        "aviso": DISCLAIMER,
        "referencia": assessment.norms.description,
        "idade": assessment.age,
        "modelo": assessment.model_key,
        "volume_intracraniano_ml": round(assessment.icv_mm3 / 1000.0, 1),
        "avisos": list(assessment.warnings),
        "estruturas": [
            {
                "id": r.structure.id,
                "nome": r.structure.title,
                "volume_ml": round(r.volume_ml, 2),
                "volume_ajustado_ml": round(r.adjusted_mm3 / 1000.0, 2),
                "z": None if r.z is None else round(r.z, 2),
                "percentil": None if r.percentile is None else round(r.percentile, 1),
                "percentil_texto": percentile_text(r),
                "marca": flag_text(r),
            }
            for r in assessment.results
        ],
    }


def run_report(args: argparse.Namespace) -> int:
    volumes = read_volumes_csv(args.csv, args.linha)
    assessment = assess(load_norms(), volumes, age=args.idade, sex=args.sexo)
    header = ReportHeader(patient_name=args.nome or "", patient_id=args.id or "", sex=args.sexo or "",
                          exam_date=args.data or "", series=args.serie or "")
    os.makedirs(args.saida, exist_ok=True)
    save_pdf(os.path.join(args.saida, "relatorio.pdf"), assessment, header)
    save_png(os.path.join(args.saida, "relatorio.png"), assessment, header)
    with open(os.path.join(args.saida, "resultado.json"), "w", encoding="utf-8") as fh:
        json.dump(result_json(assessment), fh, ensure_ascii=False, indent=1)
    flagged = [r.structure.title for r in assessment.results if r.flag]
    print(f"Relatório gravado em {args.saida}. Fora da faixa de 5 a 95: {', '.join(flagged) if flagged else 'nenhuma estrutura'}.")
    print(DISCLAIMER)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neurolaudo-volumetria", description="Volumetria cerebral com percentis por idade e sexo.")
    commands = parser.add_subparsers(dest="comando", required=True)
    report = commands.add_parser("relatorio", help="gera o relatório a partir de um CSV de volumes do SynthSeg")
    report.add_argument("--csv", required=True, help="CSV gravado por mri_synthseg --vol")
    report.add_argument("--linha", help="linha de dados (0 = primeira) ou nome do sujeito; padrão: primeira")
    report.add_argument("--idade", type=float, help="idade em anos na data do exame")
    report.add_argument("--sexo", help="F ou M")
    report.add_argument("--saida", required=True, help="pasta de saída")
    report.add_argument("--nome", help="nome a mostrar no cabeçalho")
    report.add_argument("--id", help="identificador a mostrar no cabeçalho")
    report.add_argument("--data", help="data do exame, AAAAMMDD")
    report.add_argument("--serie", help="descrição da série usada")
    report.set_defaults(run=run_report)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (ValueError, OSError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
