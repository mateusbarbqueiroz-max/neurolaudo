"""Tabelas que o SynthSeg grava (volumes e notas de qualidade) e o resultado em forma de dados."""
from __future__ import annotations

import csv

from neurolaudo.volumetry.norms import Assessment, asymmetry_percent
from neurolaudo.volumetry.report import DISCLAIMER, br, flag_text, percentile_text

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


def _volume(ml: float) -> str:
    return br(ml, 0) if ml >= 100 else br(ml, 1)


def hippocampal_asymmetry_text(assessment: Assessment) -> str:
    try:
        value = asymmetry_percent(assessment.result("hippocampus_left").volume_mm3,
                                  assessment.result("hippocampus_right").volume_mm3)
    except (KeyError, ValueError):
        return ""
    return f"Assimetria dos hipocampos de {br(abs(value), 1)} % ({'esquerdo' if value > 0 else 'direito'} maior)."


def summary_lines(assessment: Assessment) -> list[str]:
    """Uma linha por estrutura, para mostrar na tela."""
    lines = []
    for r in assessment.results:
        line = f"{r.structure.title}: {_volume(r.volume_ml)} mL"
        if r.percentile is not None:
            line += f", percentil {percentile_text(r)}"
        if r.flag:
            line += f"  {flag_text(r)}"
        lines.append(line)
    lines.append(f"Volume intracraniano total: {_volume(assessment.icv_mm3 / 1000.0)} mL")
    return lines


def report_sentence(assessment: Assessment) -> str:
    """Parágrafo pronto para colar no laudo, com a ressalva de uso em pesquisa."""
    parts = []
    for r in assessment.results:
        part = f"{r.structure.title.lower()} {_volume(r.volume_ml)} mL"
        if r.percentile is not None:
            part += f" (percentil {percentile_text(r)})"
        parts.append(part)
    basis = "percentis para a idade e o sexo" if assessment.model_key != "all" else "percentis para a idade"
    if assessment.age is None:
        basis = "sem percentis, idade não informada"
    text = (f"Volumetria cerebral automática (SynthSeg 2.0; {basis}; uso em pesquisa, não validada para diagnóstico): "
            + ", ".join(parts) + f"; volume intracraniano total {_volume(assessment.icv_mm3 / 1000.0)} mL.")
    asymmetry = hippocampal_asymmetry_text(assessment)
    return text + (" " + asymmetry if asymmetry else "")


def result_json(assessment: Assessment) -> dict:
    """O resultado em forma de dados, para o complemento do IsiX mostrar."""
    return {
        "aviso": DISCLAIMER,
        "resumo": summary_lines(assessment),
        "frase_laudo": report_sentence(assessment),
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
