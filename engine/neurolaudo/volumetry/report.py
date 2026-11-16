"""Relatório de volumetria cerebral: tabela e curvas por idade, em uma página A4.

Cada estrutura tem a sua curva (volumes em escalas muito diferentes não cabem
em um eixo só): faixa de 5 a 95, faixa de 25 a 75, mediana e o valor do
paciente. A tabela acima das curvas traz os mesmos números.

Uso em pesquisa. Não validado para diagnóstico.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import MaxNLocator, ScalarFormatter  # noqa: E402

from neurolaudo.volumetry.norms import Assessment, StructureResult, asymmetry_percent  # noqa: E402

# A fonte que acompanha o matplotlib: a página sai igual em Linux e no Mac, sem depender das fontes instaladas.
plt.rcParams["font.family"] = ["DejaVu Sans"]

DISCLAIMER = "Uso em pesquisa. Não validado para diagnóstico."

# Cores: um só tom para as faixas (clara = 5 a 95, escura = 25 a 75), tinta para o
# texto, e a cor de alerta reservada ao valor fora da faixa (sempre com rótulo).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BAND_WIDE = "#86b6ef"
BAND_NARROW = "#3987e5"
MEDIAN = "#0d366b"
ALERT = "#d03b3b"

SHORT_TITLES = {
    "hippocampus_left": "Hipocampo E",
    "hippocampus_right": "Hipocampo D",
    "amygdala_left": "Amígdala E",
    "amygdala_right": "Amígdala D",
    "thalamus_left": "Tálamo E",
    "thalamus_right": "Tálamo D",
    "lateral_ventricles": "Ventrículos lat.",
    "cortical_grey_matter": "Córtex cerebral",
    "cerebral_white_matter": "Subst. branca",
    "whole_brain": "Encéfalo",
}


@dataclass(frozen=True)
class ReportHeader:
    patient_name: str = ""
    patient_id: str = ""
    sex: str = ""
    exam_date: str = ""
    series: str = ""


def br(value: float, decimals: int = 1) -> str:
    """Número com vírgula decimal."""
    return f"{value:.{decimals}f}".replace(".", ",")


def percentile_text(result: StructureResult) -> str:
    p = result.percentile
    if p is None:
        return "–"
    if p < 1:
        return "< 1"
    if p > 99:
        return "> 99"
    return str(int(round(p)))


def flag_text(result: StructureResult) -> str:
    """Marca de valor fora da faixa: seta e palavras, nunca só cor."""
    if result.flag.startswith("abaixo"):
        return "▼ abaixo do percentil 5"
    if result.flag.startswith("acima"):
        return "▲ acima do percentil 95"
    return ""


class _CommaFormatter(ScalarFormatter):
    """Números dos eixos com vírgula decimal, como no restante da página."""

    def __init__(self):
        super().__init__(useOffset=False)

    def __call__(self, x, pos=None):
        return super().__call__(x, pos).replace(".", ",")


def _volume_text(mm3: float) -> str:
    ml = mm3 / 1000.0
    return br(ml, 0) if ml >= 100 else br(ml, 1)


def _sex_text(model_key: str) -> str:
    return {"female": "feminino", "male": "masculino"}.get(model_key, "não informado")


def _date_text(d: str) -> str:
    return f"{d[6:8]}/{d[4:6]}/{d[0:4]}" if len(d) == 8 and d.isdigit() else d


def _draw_table(ax, assessment: Assessment) -> None:
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    columns = [("Estrutura", 0.0, "left"), ("Volume (mL)", 0.44, "right"), ("% do VIC", 0.57, "right"),
               ("Percentil", 0.69, "right"), ("", 0.72, "left")]
    rows = len(assessment.results) + 1
    step = 1.0 / rows
    y = 1.0 - step / 2
    for title, x, align in columns:
        ax.text(x, y, title, ha=align, va="center", fontsize=8, color=INK_SECONDARY, fontweight="bold")
    ax.plot([0, 1], [1.0 - step, 1.0 - step], color=AXIS, linewidth=0.8)
    for i, r in enumerate(assessment.results, start=1):
        y = 1.0 - step * (i + 0.5)
        flagged = bool(r.flag)
        weight = "bold" if flagged else "normal"
        ax.text(0.0, y, r.structure.title, ha="left", va="center", fontsize=8.5, color=INK, fontweight=weight)
        ax.text(0.44, y, _volume_text(r.volume_mm3), ha="right", va="center", fontsize=8.5, color=INK, fontweight=weight)
        share = 100.0 * r.volume_mm3 / assessment.icv_mm3
        ax.text(0.57, y, br(share, 2 if share < 10 else 1), ha="right", va="center", fontsize=8.5, color=INK, fontweight=weight)
        ax.text(0.69, y, percentile_text(r), ha="right", va="center", fontsize=8.5, color=INK, fontweight=weight)
        if flagged:
            ax.plot([0.725], [y], marker="s", markersize=5, color=ALERT, clip_on=False)
            ax.text(0.745, y, flag_text(r), ha="left", va="center", fontsize=8, color=INK, fontweight="bold")
        ax.plot([0, 1], [1.0 - step * (i + 1)] * 2, color=GRID, linewidth=0.5)


def _draw_chart(ax, result: StructureResult, assessment: Assessment) -> None:
    norms = assessment.norms
    model = result.structure.models[assessment.model_key]
    ages = np.linspace(norms.age_min, norms.age_max, 80)
    a = [norms.scaled_age(float(x)) for x in ages]

    def centile(q):
        return np.array([model.centile_mm3(v, q) / 1000.0 for v in a])

    ax.set_facecolor(SURFACE)
    ax.fill_between(ages, centile(0.05), centile(0.95), color=BAND_WIDE, linewidth=0)
    ax.fill_between(ages, centile(0.25), centile(0.75), color=BAND_NARROW, linewidth=0)
    ax.plot(ages, centile(0.50), color=MEDIAN, linewidth=1.4)
    if assessment.age is not None and result.z is not None:
        color = ALERT if result.flag else INK
        ax.plot([assessment.age], [result.adjusted_mm3 / 1000.0], marker="o", markersize=7, color=color,
                markeredgecolor=SURFACE, markeredgewidth=1.6, linestyle="none", zorder=5, clip_on=False)
    # Nome em uma linha e percentil na de baixo: lado a lado, os nomes longos se sobrepõem.
    ax.set_title(SHORT_TITLES.get(result.structure.id, result.structure.title), fontsize=8, color=INK, loc="left", pad=13)
    ax.text(0.0, 1.03, f"percentil {percentile_text(result)}", transform=ax.transAxes, ha="left", va="bottom",
            fontsize=7, color=INK_SECONDARY)
    ax.set_xticks([20, 40, 60, 80])
    ax.tick_params(axis="both", labelsize=6.5, colors=INK_MUTED, length=2, width=0.5)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=3))
    ax.yaxis.set_major_formatter(_CommaFormatter())
    ax.grid(axis="y", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.6)
    low = min(norms.age_min, assessment.age) if assessment.age is not None else norms.age_min
    high = max(norms.age_max, assessment.age) if assessment.age is not None else norms.age_max
    ax.set_xlim(low - 1, high + 1)


def draw_page_title(fig, title: str, left: float = 0.08, right: float = 0.92) -> None:
    """Título da página, com o aviso de uso em pesquisa acima dele, à direita."""
    fig.text(right, 0.978, DISCLAIMER, fontsize=8.5, fontweight="bold", color=INK, va="top", ha="right")
    fig.text(left, 0.955, title, fontsize=16, fontweight="bold", color=INK, va="top")


def build_figure(assessment: Assessment, header: ReportHeader, notes=(), footnotes=()):
    """Monta a página do relatório (A4 em pé).

    `notes`: avisos do exame, mostrados em destaque logo abaixo da tabela, junto com os da avaliação.
    `footnotes`: informações do exame para o rodapé.
    """
    fig = plt.figure(figsize=(8.27, 11.69), facecolor=SURFACE)
    left, right = 0.08, 0.92

    draw_page_title(fig, "Volumetria cerebral", left, right)
    age = "idade não informada" if assessment.age is None else f"{br(assessment.age, 0)} anos"
    who = " · ".join(x for x in [header.patient_name, f"ID {header.patient_id}" if header.patient_id else "",
                                 age, f"sexo {_sex_text(assessment.model_key)}"] if x)
    exam = " · ".join(x for x in [f"Exame de {_date_text(header.exam_date)}" if header.exam_date else "",
                                  f"série {header.series}" if header.series else "",
                                  f"volume intracraniano total (VIC) {br(assessment.icv_mm3 / 1000.0, 0)} mL"] if x)
    fig.text(left, 0.925, who, fontsize=9.5, color=INK, va="top")
    fig.text(left, 0.906, exam, fontsize=8.5, color=INK_SECONDARY, va="top")

    table_ax = fig.add_axes([left, 0.615, right - left, 0.265])
    _draw_table(table_ax, assessment)

    cursor = 0.598
    try:
        asym = asymmetry_percent(assessment.result("hippocampus_left").volume_mm3,
                                 assessment.result("hippocampus_right").volume_mm3)
        side = "esquerdo maior" if asym > 0 else "direito maior"
        fig.text(left, cursor, f"Assimetria dos hipocampos: {br(abs(asym), 1)} % ({side}).", fontsize=8.5, color=INK, va="top")
    except (KeyError, ValueError):
        pass
    cursor -= 0.021
    # Avisos do exame: perto da tabela, onde são lidos. Os gráficos encolhem para dar lugar.
    for warning in list(assessment.warnings) + list(notes):
        for n, piece in enumerate(textwrap.wrap(warning, 112)):
            if n == 0:
                fig.text(left, cursor, "!", fontsize=8, color=ALERT, va="top", fontweight="bold")
            fig.text(left + 0.012, cursor, piece, fontsize=8, color=INK, va="top")
            cursor -= 0.0145
        cursor -= 0.002

    handles = [Patch(facecolor=BAND_WIDE, label="percentis 5 a 95"), Patch(facecolor=BAND_NARROW, label="percentis 25 a 75"),
               Line2D([0], [0], color=MEDIAN, linewidth=1.4, label="mediana"),
               Line2D([0], [0], marker="o", color=INK, markeredgecolor=SURFACE, markersize=7, linestyle="none", label="paciente"),
               Line2D([0], [0], marker="o", color=ALERT, markeredgecolor=SURFACE, markersize=7, linestyle="none",
                      label="paciente, fora de 5 a 95")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(left - 0.008, cursor - 0.005), ncol=5, frameon=False,
               fontsize=7.5, labelcolor=INK_SECONDARY, handlelength=1.6, columnspacing=1.4)

    grid = fig.add_gridspec(2, 5, left=left, right=right, top=cursor - 0.072, bottom=0.205, wspace=0.42, hspace=0.55)
    for index, result in enumerate(assessment.results[:10]):
        ax = fig.add_subplot(grid[index // 5, index % 5])
        _draw_chart(ax, result, assessment)
        if index // 5 == 1:
            ax.set_xlabel("idade (anos)", fontsize=6.5, color=INK_MUTED, labelpad=2)
        if index % 5 == 0:
            ax.set_ylabel("volume ajustado (mL)", fontsize=6.5, color=INK_MUTED, labelpad=2)

    lines = ["Percentil para a idade e o sexo, com o volume ajustado ao volume intracraniano (VIC).",
             f"Referência: {assessment.norms.description}; "
             f"{br(assessment.norms.age_min, 0)} a {br(assessment.norms.age_max, 0)} anos.",
             "As curvas mostram o volume ajustado a um volume intracraniano de "
             f"{br(assessment.norms.reference_icv_mm3 / 1000.0, 0)} mL.",
             "Limites: entre aparelhos o resultado pode deslocar até cerca de 0,5 desvio-padrão; nas estruturas "
             "pequenas, o enquadramento da imagem muda o volume em 1 a 3 %; medida de um único momento, não mede "
             "perda ao longo do tempo."]
    lines += list(footnotes)
    y = 0.165
    for line in lines:
        for piece in textwrap.wrap(line, 118):
            fig.text(left, y, piece, fontsize=7.5, color=INK_SECONDARY, va="top")
            y -= 0.015
        y -= 0.004
    fig.text(left, 0.045, DISCLAIMER + " Normas derivadas do conjunto IXI (CC BY-SA 3.0), via Neurodesk.",
             fontsize=7.5, color=INK, va="top", fontweight="bold")
    return fig


def patient_line(assessment: Assessment, header: ReportHeader) -> str:
    """Linha de identificação, para as outras páginas do relatório."""
    age = "" if assessment.age is None else f"{br(assessment.age, 0)} anos"
    return " · ".join(x for x in [header.patient_name, f"ID {header.patient_id}" if header.patient_id else "", age,
                                  f"exame de {_date_text(header.exam_date)}" if header.exam_date else ""] if x)


def save_figures_pdf(path: str, figures) -> None:
    """Grava as páginas em um único PDF."""
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(path) as pdf:
        for fig in figures:
            pdf.savefig(fig, facecolor=fig.get_facecolor())


def figure_rgba(fig, dpi: int = 150) -> np.ndarray:
    """A página como matriz RGBA (linhas, colunas, 4), para gravar como imagem DICOM."""
    fig.set_dpi(dpi)
    fig.canvas.draw()
    return np.ascontiguousarray(np.asarray(fig.canvas.buffer_rgba()))


def save_pdf(path: str, assessment: Assessment, header: ReportHeader, notes=(), footnotes=()) -> None:
    fig = build_figure(assessment, header, notes, footnotes)
    try:
        save_figures_pdf(path, [fig])
    finally:
        plt.close(fig)


def save_png(path: str, assessment: Assessment, header: ReportHeader, dpi: int = 150, notes=(), footnotes=()) -> None:
    fig = build_figure(assessment, header, notes, footnotes)
    try:
        fig.savefig(path, format="png", dpi=dpi, facecolor=fig.get_facecolor())
    finally:
        plt.close(fig)


def render_rgb(assessment: Assessment, header: ReportHeader, dpi: int = 120) -> np.ndarray:
    """A página como matriz RGB (linhas, colunas, 3)."""
    fig = build_figure(assessment, header)
    try:
        return np.ascontiguousarray(figure_rgba(fig, dpi)[:, :, :3])
    finally:
        plt.close(fig)
