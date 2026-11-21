"""Resume a repetição da volumetria medida por validate_retest.py: quanto um volume varia só por repetir o exame.

Uso: python retest_summary.py PASTA_COM_OS_JSON PASTA_DE_SAIDA

Dois cenários, com o logaritmo dos volumes (diferenças em %):
  - mesmo aparelho: pessoas escaneadas várias vezes no mesmo aparelho;
  - aparelhos diferentes: a mesma pessoa em aparelhos diferentes (a primeira sessão de cada um).
Para cada estrutura, o desvio dentro da pessoa (dp) e o limite de 95 % para a diferença entre dois exames
(2,77 × dp, o "coeficiente de repetibilidade"): diferença maior que o limite raramente vem só da repetição.

Grava repeticao.json (lido pelo motor para comparar exames), repeticao.txt (para ler) e repeticao-exames.csv.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

from neurolaudo.volumetry.norms import load_norms

FACTOR = 1.96 * math.sqrt(2.0)   # limite de 95 % para a diferença entre duas medidas
VARIANTS = {"ajustado": ("ajustados_mm3", "Volume ajustado ao intracraniano (o dos percentis)"),
            "bruto": ("volumes_mm3", "Volume bruto")}
SCENARIOS = {"mesmo_aparelho": "Mesmo aparelho", "aparelhos_diferentes": "Aparelhos diferentes"}


def br(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def groups(records: list[dict]) -> dict[str, list[list[dict]]]:
    """Exames agrupados por pessoa em cada cenário."""
    same: dict[tuple, list[dict]] = defaultdict(list)
    first: dict[tuple, dict] = {}
    for r in records:
        same[(r["sujeito"], r["aparelho"])].append(r)
        key = (r["sujeito"], r["aparelho"])
        if key not in first or r["repeticao"] < first[key]["repeticao"]:
            first[key] = r
    across: dict[str, list[dict]] = defaultdict(list)
    for (subject, _), r in sorted(first.items()):
        across[subject].append(r)
    return {"mesmo_aparelho": [g for g in same.values() if len(g) >= 2],
            "aparelhos_diferentes": [g for g in across.values() if len(g) >= 2]}


def within(group_values: list[list[float]]) -> dict:
    """Desvio dentro da pessoa (do logaritmo), juntando as pessoas, e a conferência pelos pares."""
    squares, freedom = 0.0, 0
    for values in group_values:
        logs = [math.log(v) for v in values]
        mean = sum(logs) / len(logs)
        squares += sum((x - mean) ** 2 for x in logs)
        freedom += len(logs) - 1
    sd = math.sqrt(squares / freedom) if freedom else float("nan")
    limit = FACTOR * sd
    pairs = [abs(math.log(a) - math.log(b)) for values in group_values for a, b in combinations(values, 2)]
    return {"dp_pct": round(100 * sd, 2), "limite_pct": round(100 * limit, 2), "grupos": len(group_values),
            "exames": sum(len(v) for v in group_values), "pares": len(pairs),
            "pares_acima": sum(1 for d in pairs if d > limit)}


def main(argv: list[str]) -> int:
    folder, out = Path(argv[1]), Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.rglob("*_*.json"))]
    records = [r for r in records if "volumes_mm3" in r]
    if not records:
        print("Nenhum exame medido.")
        return 1
    norms = load_norms()
    ids = [s.id for s in norms.structures]
    titles = {s.id: s.title for s in norms.structures} | {"icv": "Volume intracraniano"}
    grouped = groups(records)

    variants: dict[str, dict] = {}
    for variant, (field, _) in VARIANTS.items():
        table = {}
        for sid in ids + (["icv"] if variant == "bruto" else []):
            def value(r):
                return r["icv_mm3"] if sid == "icv" else r[field][sid]
            table[sid] = {scenario: within([[value(r) for r in g] for g in grouped[scenario]]) for scenario in SCENARIOS}
        variants[variant] = table
    # A medida usada para comparar exames: a que varia menos entre aparelhos diferentes, em média.
    mean_limit = {v: sum(variants[v][sid]["aparelhos_diferentes"]["limite_pct"] for sid in ids) / len(ids) for v in variants}
    chosen = min(mean_limit, key=mean_limit.get)

    subjects = sorted({r["sujeito"] for r in records})
    summary = {
        "fonte": "ON-Harmony (OpenNeuro ds004712, CC0; Warrington et al., Scientific Data, 2025): "
                 f"{len(subjects)} adultos saudáveis de 19 a 50 anos, aparelhos de 3 T Siemens, Philips e GE",
        "gerado_em": date.today().isoformat(),
        "pessoas": len(subjects), "exames": len(records),
        "medida": chosen,
        "explicacao": "limite_pct: diferença entre dois exames da mesma pessoa que só a repetição explica em 95 % "
                      "das vezes (2,77 × dp, no logaritmo do volume)",
        "variantes": variants,
    }
    (out / "repeticao.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"Repetição da volumetria: {len(records)} exames de {len(subjects)} voluntários públicos (ON-Harmony, CC0).",
             "Limite: diferença entre dois exames da mesma pessoa que só a repetição explica em 95 % das vezes.",
             "Pares acima: quantos pares de exames da mesma pessoa passaram do limite (esperado: cerca de 5 %).", ""]
    for variant, (_, caption) in VARIANTS.items():
        lines.append(caption + (" (usado para comparar exames)" if variant == chosen else ""))
        lines.append(f"{'':28s}" + "".join(f"{SCENARIOS[s]:>36s}" for s in SCENARIOS))
        for sid, row in variants[variant].items():
            cells = "".join(f"   dp {br(c['dp_pct']):>4s} %  limite ±{br(c['limite_pct']):>4s} %  acima {c['pares_acima']:>3d}/{c['pares']:<3d}"
                            for c in (row[s] for s in SCENARIOS))
            lines.append(f"{titles[sid]:28s}{cells}")
        lines.append("")
    # Diferença média de cada aparelho em relação à média da pessoa: mostra o quanto o aparelho puxa para um lado.
    scanners = sorted({r["aparelho"] for g in grouped["aparelhos_diferentes"] for r in g})
    lines.append("Diferença média de cada aparelho para a média da pessoa, em % (volume ajustado; primeira sessão):")
    lines.append(f"{'':28s}" + "".join(f"{s:>9s}" for s in scanners))
    for sid in ids:
        offsets: dict[str, list[float]] = defaultdict(list)
        for g in grouped["aparelhos_diferentes"]:
            logs = {r["aparelho"]: math.log(r["ajustados_mm3"][sid]) for r in g}
            mean = sum(logs.values()) / len(logs)
            for scanner, x in logs.items():
                offsets[scanner].append(100 * (x - mean))
        lines.append(f"{titles[sid]:28s}" + "".join(
            f"{br(sum(offsets[s]) / len(offsets[s])):>9s}" if offsets[s] else f"{'-':>9s}" for s in scanners))
    text = "\n".join(lines)
    print(text)
    (out / "repeticao.txt").write_text(text + "\n", encoding="utf-8")

    with open(out / "repeticao-exames.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["sujeito", "sessao", "aparelho", "repeticao", "sexo", "idade", "icv_mm3", "segmentacoes", "tempo_s"]
                        + [f"{sid}_mm3" for sid in ids])
        for r in records:
            writer.writerow([r["sujeito"], r["sessao"], r["aparelho"], r["repeticao"], r["sexo"], r["idade"],
                             round(r["icv_mm3"], 1), r["segmentacoes"], r["tempo_s"]]
                            + [round(r["volumes_mm3"][sid], 1) for sid in ids])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
