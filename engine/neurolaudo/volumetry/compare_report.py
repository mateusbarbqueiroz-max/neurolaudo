"""Página do relatório com a comparação com o exame anterior. Uso em pesquisa, não validado para diagnóstico.

Tabela com o volume de cada estrutura nos dois exames, a variação, a taxa por ano e a variação que só a
repetição do exame produz; embaixo, a trajetória de cada estrutura sobre as faixas da referência, na idade
do paciente.
"""
from __future__ import annotations

import textwrap
from typing import Mapping, Sequence

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from neurolaudo.volumetry import history
from neurolaudo.volumetry.norms import Norms
from neurolaudo.volumetry.report import (ALERT, AXIS, BAND_NARROW, BAND_WIDE, DISCLAIMER, GRID, INK, INK_MUTED,
                                         INK_SECONDARY, MEDIAN, SHORT_TITLES, SURFACE, WARNINGS_FLOOR, _CommaFormatter,
                                         br, draw_page_title, plt)

MARK_TEXT = {"redução": "▼ redução", "aumento": "▲ aumento"}


def _draw_table(ax, rows: Sequence[Mapping]) -> None:
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    columns = [("Estrutura", 0.0, "left"), ("Anterior (mL)", 0.43, "right"), ("Atual (mL)", 0.55, "right"),
               ("Variação", 0.66, "right"), ("Por ano", 0.76, "right"), ("Repetição", 0.875, "right"), ("", 0.895, "left")]
    step = 1.0 / (len(rows) + 1)
    y = 1.0 - step / 2
    for title, x, align in columns:
        ax.text(x, y, title, ha=align, va="center", fontsize=8, color=INK_SECONDARY, fontweight="bold")
    ax.plot([0, 1], [1.0 - step, 1.0 - step], color=AXIS, linewidth=0.8)
    for i, row in enumerate(rows, start=1):
        y = 1.0 - step * (i + 0.5)
        weight = "bold" if row["marca"] else "normal"
        rate = "–" if row["por_ano_pct"] is None else f"{history.signed(row['por_ano_pct'])} %"
        limit = "–" if row["limite_pct"] is None else f"±{br(row['limite_pct'])} %"
        cells = [(row["nome"], 0.0, "left"), (br(row["anterior_ml"], 2 if row["anterior_ml"] < 100 else 0), 0.43, "right"),
                 (br(row["atual_ml"], 2 if row["atual_ml"] < 100 else 0), 0.55, "right"),
                 (f"{history.signed(row['variacao_pct'])} %", 0.66, "right"), (rate, 0.76, "right"), (limit, 0.875, "right")]
        for text, x, align in cells:
            ax.text(x, y, text, ha=align, va="center", fontsize=8.5, color=INK, fontweight=weight)
        if row["marca"]:
            ax.plot([0.9], [y], marker="s", markersize=5, color=ALERT, clip_on=False)
            ax.text(0.915, y, MARK_TEXT[row["marca"]], ha="left", va="center", fontsize=8, color=INK, fontweight="bold")
        ax.plot([0, 1], [1.0 - step * (i + 1)] * 2, color=GRID, linewidth=0.5)


def _draw_trend(ax, norms: Norms, structure_id: str, model_key: str, points: Sequence[tuple[float, float]],
                row: Mapping) -> None:
    """Volume ajustado de cada exame na idade do paciente, sobre as faixas da referência."""
    model = norms.structure(structure_id).models[model_key]
    ages = [p[0] for p in points]
    xs = np.linspace(min(ages) - 4, max(ages) + 4, 40)
    a = [norms.scaled_age(float(x)) for x in xs]

    def centile(q):
        return np.array([model.centile_mm3(v, q) / 1000.0 for v in a])

    ax.set_facecolor(SURFACE)
    ax.fill_between(xs, centile(0.05), centile(0.95), color=BAND_WIDE, linewidth=0)
    ax.fill_between(xs, centile(0.25), centile(0.75), color=BAND_NARROW, linewidth=0)
    ax.plot(xs, centile(0.50), color=MEDIAN, linewidth=1.4)
    ax.plot(ages, [p[1] for p in points], color=INK, linewidth=1.0, zorder=4)
    for age, value in points[:-1]:
        ax.plot([age], [value], marker="o", markersize=6, markerfacecolor=SURFACE, markeredgecolor=INK,
                markeredgewidth=1.2, linestyle="none", zorder=5, clip_on=False)
    ax.plot([points[-1][0]], [points[-1][1]], marker="o", markersize=7, color=ALERT if row["marca"] else INK,
            markeredgecolor=SURFACE, markeredgewidth=1.6, linestyle="none", zorder=6, clip_on=False)
    ax.set_title(SHORT_TITLES.get(structure_id, row["nome"]), fontsize=8, color=INK, loc="left", pad=13)
    ax.text(0.0, 1.03, f"{history.signed(row['variacao_pct'])} %", transform=ax.transAxes, ha="left", va="bottom",
            fontsize=7, color=INK_SECONDARY)
    ax.tick_params(axis="both", labelsize=6.5, colors=INK_MUTED, length=2, width=0.5)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=3, integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=3))
    ax.yaxis.set_major_formatter(_CommaFormatter())
    ax.grid(axis="y", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.6)
    ax.set_xlim(xs[0], xs[-1])


def build_comparison_figure(norms: Norms, comparison: Mapping, records: Sequence[Mapping], who: str,
                            repeatability: Mapping | None):
    """A página A4 da comparação. `records`: os exames do paciente, do mais antigo ao atual."""
    fig = plt.figure(figsize=(8.27, 11.69), facecolor=SURFACE)
    left, right = 0.08, 0.92
    draw_page_title(fig, "Volumetria: comparação com o exame anterior", left, right)
    prior = comparison["anterior"]
    scenario = history.SCENARIO_TEXT[comparison["cenario"]]
    fig.text(left, 0.925, who, fontsize=9.5, color=INK, va="top")
    fig.text(left, 0.906, " · ".join(x for x in [f"Exame anterior de {history.date_text(prior['data'])}",
                                                 f"série {prior['serie']}" if prior["serie"] else "",
                                                 f"intervalo de {comparison['intervalo']}",
                                                 f"repetição: {scenario}"] if x),
             fontsize=8.5, color=INK_SECONDARY, va="top")

    rows = comparison["estruturas"]
    _draw_table(fig.add_axes([left, 0.615, right - left, 0.265]), rows)

    cursor = 0.598
    notes = list(comparison["avisos"])
    for index, note in enumerate(notes):
        pieces = textwrap.wrap(note, 112)
        if cursor - 0.0145 * (len(pieces) + 1) < WARNINGS_FLOOR:
            fig.text(left, cursor, "!", fontsize=8, color=ALERT, va="top", fontweight="bold")
            fig.text(left + 0.012, cursor, f"Mais {len(notes) - index} aviso(s): veja a lista completa na tela do NeuroLaudo.",
                     fontsize=8, color=INK, va="top")
            cursor -= 0.0165
            break
        for n, piece in enumerate(pieces):
            if n == 0:
                fig.text(left, cursor, "!", fontsize=8, color=ALERT, va="top", fontweight="bold")
            fig.text(left + 0.012, cursor, piece, fontsize=8, color=INK, va="top")
            cursor -= 0.0145
        cursor -= 0.002

    model_key = records[-1].get("sexo") or "all"
    dated = [r for r in records if r.get("idade") is not None]
    if len(dated) >= 2 and dated[-1] is records[-1]:
        handles = [Patch(facecolor=BAND_WIDE, label="percentis 5 a 95"), Patch(facecolor=BAND_NARROW, label="percentis 25 a 75"),
                   Line2D([0], [0], color=MEDIAN, linewidth=1.4, label="mediana"),
                   Line2D([0], [0], marker="o", markerfacecolor=SURFACE, markeredgecolor=INK, markersize=6, linestyle="none",
                          label="exames anteriores"),
                   Line2D([0], [0], marker="o", color=INK, markeredgecolor=SURFACE, markersize=7, linestyle="none", label="atual"),
                   Line2D([0], [0], marker="o", color=ALERT, markeredgecolor=SURFACE, markersize=7, linestyle="none",
                          label="atual, além da repetição")]
        fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(left - 0.008, cursor - 0.005), ncol=6, frameon=False,
                   fontsize=7, labelcolor=INK_SECONDARY, handlelength=1.4, columnspacing=1.0)
        grid = fig.add_gridspec(2, 5, left=left, right=right, top=cursor - 0.072, bottom=0.215, wspace=0.42, hspace=0.55)
        for index, row in enumerate(rows[:10]):
            points = [(float(r["idade"]), history.adjusted_mm3(norms, r, row["id"], model_key) / 1000.0) for r in dated
                      if r["volumes_mm3"].get(row["id"])]
            if len(points) < 2:
                continue
            ax = fig.add_subplot(grid[index // 5, index % 5])
            _draw_trend(ax, norms, row["id"], model_key, points, row)
            if index // 5 == 1:
                ax.set_xlabel("idade (anos)", fontsize=6.5, color=INK_MUTED, labelpad=2)
            if index % 5 == 0:
                ax.set_ylabel("volume ajustado (mL)", fontsize=6.5, color=INK_MUTED, labelpad=2)
    else:
        fig.text(left, cursor - 0.01, "Idade desconhecida em um dos exames: sem gráficos de trajetória.",
                 fontsize=8.5, color=INK_SECONDARY, va="top")

    measured = "volume ajustado ao volume intracraniano de cada exame (o mesmo dos percentis)" \
        if comparison["medida"] == "ajustado" else "volume medido, sem ajuste"
    lines = [f"Variação: diferença do {measured} entre o exame anterior e o atual. Por ano: a mesma variação "
             "convertida para 12 meses (só com intervalo de 6 meses ou mais)."]
    if repeatability:
        lines.append("Repetição: maior variação que só a repetição do exame produz em 95 % das vezes, medida em "
                     f"{repeatability.get('pessoas', '?')} voluntários escaneados várias vezes ({repeatability.get('fonte', '')}). "
                     f"Usado o limite de {scenario}. Variação menor que esse limite pode ser só a imprecisão da medida.")
    lines.append("Os gráficos mostram o volume ajustado de cada exame do paciente medido neste Mac, na idade de cada exame.")
    y = 0.172
    for line in lines:
        for piece in textwrap.wrap(line, 118):
            fig.text(left, y, piece, fontsize=7.5, color=INK_SECONDARY, va="top")
            y -= 0.015
        y -= 0.004
    fig.text(left, 0.045, DISCLAIMER + " Comparação entre exames: não validada.", fontsize=7.5, color=INK, va="top",
             fontweight="bold")
    return fig
