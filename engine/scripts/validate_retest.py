"""Roda a volumetria em todos os exames de uma pessoa escaneada várias vezes, para medir a repetição.

Uso: python validate_retest.py PASTA_DA_PESSOA PASTA_DE_SAIDA --sujeito ID --sexo F --idade 25

A PASTA_DA_PESSOA tem um T1 por sessão, com o nome da sessão (por exemplo OXF1PRI002.nii.gz). Para cada
um roda a volumetria completa, a mesma do complemento, e grava em PASTA_DE_SAIDA/ID_SESSAO.json os
volumes medidos, sem arredondar. O resumo de todas as pessoas sai de retest_summary.py.

Feito para o ON-Harmony (OpenNeuro ds004712, CC0): adultos de 19 a 50 anos, cada um escaneado em 6
aparelhos de 3 T de três fabricantes; 10 deles, mais 5 vezes no mesmo aparelho. O nome da sessão diz o
aparelho (OXF1PRI) e a repetição (002).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from neurolaudo.volumetry.norms import assess, load_norms
from neurolaudo.volumetry.pipeline import run_exam
from neurolaudo.volumetry.report import ReportHeader
from neurolaudo.volumetry.tables import read_volumes_csv


def measure(path: Path, out: Path, subject: str, sex: str, age: float, norms) -> dict:
    session = path.name[:-len(".nii.gz")]
    folder = out / "trabalho" / session
    result = run_exam(str(path), str(folder), age=age, sex=sex,
                      header=ReportHeader(patient_name=f"Voluntário público {subject}", series=f"T1 ({session})"),
                      progress=lambda fraction, message: None, refine=True)
    volumes = read_volumes_csv(str(folder / "trabalho" / "volumes.csv"))
    assessment = assess(norms, volumes, age=age, sex=sex)
    record = {
        "sujeito": subject, "sessao": session, "aparelho": session[:-3], "repeticao": session[-3:],
        "sexo": sex, "idade": age,
        "icv_mm3": assessment.icv_mm3,
        "volumes_mm3": {r.structure.id: r.volume_mm3 for r in assessment.results},
        "ajustados_mm3": {r.structure.id: r.adjusted_mm3 for r in assessment.results},
        "voxels": result["entrada"]["voxels"], "voxel_mm": result["entrada"]["voxel_mm"],
        "segmentacoes": result["recorte"]["segmentacoes"], "tempo_s": result["tempos_s"]["total"],
        "avisos": result["avisos"],
    }
    (out / f"{subject}_{session}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(folder, ignore_errors=True)   # só o resumo interessa; as imagens ocupam espaço
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pasta", type=Path)
    parser.add_argument("saida", type=Path)
    parser.add_argument("--sujeito", required=True)
    parser.add_argument("--sexo", required=True)
    parser.add_argument("--idade", type=float, required=True)
    args = parser.parse_args(argv)
    args.saida.mkdir(parents=True, exist_ok=True)
    norms = load_norms()
    paths = sorted(args.pasta.glob("*.nii.gz"))
    failures = 0
    for path in paths:
        try:
            record = measure(path, args.saida, args.sujeito, args.sexo, args.idade, norms)
        except Exception as error:   # um exame ruim não pode derrubar os outros
            failures += 1
            print(f"{args.sujeito} {path.name}: falhou ({error})", flush=True)
            continue
        hippocampi = (record["volumes_mm3"]["hippocampus_left"] + record["volumes_mm3"]["hippocampus_right"]) / 1000
        print(f"{args.sujeito} {record['sessao']:11s} ICV {record['icv_mm3'] / 1000:7.1f} mL  hipocampos {hippocampi:5.2f} mL  "
              f"{record['segmentacoes']} segmentações, {record['tempo_s']:.0f} s", flush=True)
    print(f"{len(paths) - failures} de {len(paths)} exame(s) medidos.")
    return 0 if paths and failures < len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())
