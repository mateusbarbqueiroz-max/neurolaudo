"""Resume a repetição do volume de lesões de substância branca (WMH-SynthSeg) em voluntários escaneados várias vezes.

Uso: python lesion_retest_summary.py PASTA_COM_OS_JSON PASTA_DE_SAIDA

Cada JSON (um por exame) tem sujeito, sessao, aparelho, repeticao e os números do wmh_lowmem.py. Mostra:
  - o volume de cada pessoa em cada aparelho (primeira sessão);
  - a diferença média de cada aparelho para a média da pessoa, em mL;
  - o desvio dentro da pessoa, em mL, no mesmo aparelho e entre aparelhos, e o limite de 95 % para a
    diferença entre dois exames (2,77 × desvio).
Em voluntários saudáveis o volume é pequeno; por isso tudo em mL, não em %.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

FACTOR = 1.96 * math.sqrt(2.0)


def br(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def within_sd(groups: list[list[float]]) -> tuple[float, int]:
    squares, freedom = 0.0, 0
    for values in groups:
        mean = sum(values) / len(values)
        squares += sum((v - mean) ** 2 for v in values)
        freedom += len(values) - 1
    return (math.sqrt(squares / freedom) if freedom else float("nan")), sum(len(v) for v in groups)


def main(argv: list[str]) -> int:
    folder, out = Path(argv[1]), Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.rglob("*.json"))]
    records = [r for r in records if "lesoes_ml" in r]
    if not records:
        print("Nenhum exame medido.")
        return 1
    same: dict[tuple, list[dict]] = defaultdict(list)
    first: dict[tuple, dict] = {}
    for r in records:
        key = (r["sujeito"], r["aparelho"])
        same[key].append(r)
        if key not in first or r["repeticao"] < first[key]["repeticao"]:
            first[key] = r
    across: dict[str, list[dict]] = defaultdict(list)
    for (subject, _), r in sorted(first.items()):
        across[subject].append(r)
    scanners = sorted({r["aparelho"] for r in records})
    lines = [f"Volume de lesões (WMH-SynthSeg, soma das probabilidades) em {len(records)} exames de "
             f"{len(across)} voluntários públicos saudáveis (ON-Harmony, CC0).", ""]
    summary = {"exames": len(records), "pessoas": len(across), "medidas": {}}
    for field, caption in (("lesoes_ml", "soma das probabilidades"), ("lesoes_rotuladas_ml", "voxels rotulados")):
        sd_same, n_same = within_sd([[r[field] for r in g] for g in same.values() if len(g) >= 2])
        sd_across, n_across = within_sd([[r[field] for r in g] for g in across.values() if len(g) >= 2])
        values = sorted(r[field] for r in first.values())
        median = values[len(values) // 2]
        summary["medidas"][field] = {"mesmo_aparelho": {"dp_ml": round(sd_same, 2), "limite_ml": round(FACTOR * sd_same, 2), "exames": n_same},
                                     "aparelhos_diferentes": {"dp_ml": round(sd_across, 2), "limite_ml": round(FACTOR * sd_across, 2), "exames": n_across},
                                     "mediana_ml": round(median, 2), "minimo_ml": round(values[0], 2), "maximo_ml": round(values[-1], 2)}
        lines += [f"Lesões ({caption}): mediana {br(median, 2)} mL (de {br(values[0], 2)} a {br(values[-1], 2)} mL)",
                  f"  mesmo aparelho: dp {br(sd_same, 2)} mL, limite ±{br(FACTOR * sd_same, 2)} mL ({n_same} exames)",
                  f"  aparelhos diferentes: dp {br(sd_across, 2)} mL, limite ±{br(FACTOR * sd_across, 2)} mL ({n_across} exames)", ""]
    offsets: dict[str, list[float]] = defaultdict(list)
    for g in across.values():
        mean = sum(r["lesoes_ml"] for r in g) / len(g)
        for r in g:
            offsets[r["aparelho"]].append(r["lesoes_ml"] - mean)
    summary["diferenca_por_aparelho_ml"] = {s: round(sum(v) / len(v), 2) for s, v in offsets.items() if v}
    lines.append("Diferença média de cada aparelho para a média da pessoa (mL; primeira sessão):")
    lines.append("  " + "  ".join(f"{s} {br(summary['diferenca_por_aparelho_ml'].get(s, float('nan')), 2)}" for s in scanners))
    lines += ["", "Volume de cada pessoa em cada aparelho (mL; primeira sessão):", "pessoa  " + " ".join(f"{s:>8s}" for s in scanners)]
    for subject, g in sorted(across.items()):
        by = {r["aparelho"]: r["lesoes_ml"] for r in g}
        lines.append(f"{subject:7s} " + " ".join(f"{br(by[s], 2):>8s}" if s in by else f"{'-':>8s}" for s in scanners))
    times = [r.get("tempo_s", 0) for r in records]
    memory = [r.get("memoria_gb", 0) for r in records]
    lines += ["", f"Tempo médio por exame: {sum(times) / len(times):.0f} s; memória máxima: {max(memory):.1f} GB."]
    text = "\n".join(lines)
    print(text)
    (out / "lesoes-repeticao.txt").write_text(text + "\n", encoding="utf-8")
    (out / "lesoes-repeticao.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
