"""Tabelas que o SynthSeg grava (volumes e notas de qualidade) e o resultado em forma de dados."""
from __future__ import annotations

import csv

from neurolaudo.volumetry.norms import Assessment
from neurolaudo.volumetry.report import DISCLAIMER, flag_text, percentile_text

QC_TITLES_PT = {
    "general white matter": "substância branca",
    "general grey matter": "substância cinzenta",
    "general csf": "liquor",
    "cerebellum": "cerebelo",
    "brainstem": "tronco encefálico",
    "thalamus": "tálamo",
    "putamen+pallidum": "putâmen e pálido",
    "hippocampus+amygdala": "hipocampo e amígdala",
}


def read_volumes_csv(path: str, row: str | None = None) -> dict[str, float]:
    """Lê uma linha de uma tabela do SynthSeg. `row`: número da linha de dados (0 = primeira) ou o nome do sujeito.

    Serve para a tabela de volumes (mm³) e para a de notas de qualidade. Colunas sem número são ignoradas.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"a tabela {path} está vazia")
    first_column = next(iter(rows[0]))
    if row is None:
        chosen = rows[0]
    elif row.isdigit():
        index = int(row)
        if index >= len(rows):
            raise ValueError(f"a tabela tem {len(rows)} linha(s) de dados; não existe a linha {index}")
        chosen = rows[index]
    else:
        matches = [r for r in rows if r[first_column] == row]
        if not matches:
            raise ValueError(f"não há linha com '{row}' na coluna '{first_column}'")
        chosen = matches[0]
    values: dict[str, float] = {}
    for key, value in chosen.items():
        if key is None:
            continue
        try:
            values[key.strip()] = float(value)
        except (TypeError, ValueError):
            continue
    return values


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
