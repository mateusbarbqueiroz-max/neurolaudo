"""Mapa colorido da segmentação: para conferir, com os olhos, o que foi medido.

Duas saídas:
- `render_map`: todos os cortes na grade da série original, em RGBA, para o
  complemento gravar como série colorida ao lado do T1;
- `montage_figure`: uma página com cortes axiais, coronais e sagitais.

Estruturas pares do relatório (hipocampo, amígdala, tálamo) têm uma cor para
cada lado. Assim uma troca de lado aparece na imagem em vez de passar calada.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import nibabel as nib  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from neurolaudo.volumetry.report import DISCLAIMER, INK, INK_SECONDARY, SURFACE, draw_page_title  # noqa: E402

# Rótulo do SynthSeg -> (R, G, B, opacidade). Rótulos fora da tabela ficam sem cor.
LABEL_STYLE: dict[int, tuple[int, int, int, float]] = {
    2: (245, 245, 245, 0.12), 41: (245, 245, 245, 0.12),    # substância branca cerebral
    3: (205, 62, 78, 0.30), 42: (205, 62, 78, 0.30),        # córtex cerebral
    4: (170, 70, 220, 0.55), 43: (170, 70, 220, 0.55),      # ventrículos laterais
    5: (170, 70, 220, 0.55), 44: (170, 70, 220, 0.55),      # cornos temporais
    7: (220, 248, 164, 0.25), 46: (220, 248, 164, 0.25),    # substância branca do cerebelo
    8: (230, 148, 34, 0.25), 47: (230, 148, 34, 0.25),      # córtex do cerebelo
    10: (40, 190, 70, 0.55), 49: (160, 235, 60, 0.55),      # tálamo E, D
    11: (122, 186, 220, 0.45), 50: (122, 186, 220, 0.45),   # caudado
    12: (236, 13, 176, 0.45), 51: (236, 13, 176, 0.45),     # putâmen
    13: (12, 48, 255, 0.45), 52: (12, 48, 255, 0.45),       # pálido
    14: (204, 182, 142, 0.45), 15: (42, 204, 164, 0.45),    # III e IV ventrículos
    16: (119, 159, 176, 0.30),                              # tronco
    17: (240, 220, 30, 0.60), 53: (255, 140, 0, 0.60),      # hipocampo E, D
    18: (90, 235, 235, 0.60), 54: (40, 130, 255, 0.60),     # amígdala E, D
    26: (255, 165, 0, 0.45), 58: (255, 165, 0, 0.45),       # accumbens
    28: (165, 42, 42, 0.35), 60: (165, 42, 42, 0.35),       # diencéfalo ventral
}

LEGEND = [(17, "Hipocampo E"), (53, "Hipocampo D"), (18, "Amígdala E"), (54, "Amígdala D"), (10, "Tálamo E"),
          (49, "Tálamo D"), (4, "Ventrículos laterais"), (3, "Córtex cerebral"), (2, "Substância branca")]

SAGITTAL_CAPTIONS = ["hipocampo D", "tálamo D", "tálamo E", "hipocampo E"]
HIPPOCAMPUS_LEFT, HIPPOCAMPUS_RIGHT = 17, 53
THALAMUS_LEFT, THALAMUS_RIGHT = 10, 49
LATERAL_VENTRICLES = (4, 43)


def _lookup() -> tuple[np.ndarray, np.ndarray]:
    colors = np.zeros((256, 3), dtype=np.float32)
    alpha = np.zeros(256, dtype=np.float32)
    for label, (r, g, b, a) in LABEL_STYLE.items():
        colors[label] = (r, g, b)
        alpha[label] = a
    return colors, alpha


def to_gray(data: np.ndarray) -> np.ndarray:
    """Tons de cinza de 0 a 255, com a janela entre os percentis 0,5 e 99,5."""
    values = np.asarray(data, dtype=np.float32)
    low, high = np.percentile(values, [0.5, 99.5])
    if not high > low:
        return np.zeros(values.shape, dtype=np.uint8)
    return (np.clip((values - low) / (high - low), 0.0, 1.0) * 255.0).astype(np.uint8)


def blend(gray: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Mistura a cor de cada rótulo sobre o cinza. Devolve RGB uint8, com um eixo a mais no fim."""
    colors, alpha = _lookup()
    index = np.where((labels >= 0) & (labels < 256), labels, 0).astype(np.intp)
    a = alpha[index][..., None]
    rgb = gray[..., None].astype(np.float32) * (1.0 - a) + colors[index] * a
    return np.clip(rgb + 0.5, 0, 255).astype(np.uint8)


def render_map(image_data: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Mapa colorido na grade de entrada, como RGBA de forma (cortes, linhas, colunas, 4).

    O volume vem indexado [coluna, linha, corte], como no NIfTI que o complemento grava.
    """
    if image_data.shape[:3] != labels.shape[:3]:
        raise ValueError("imagem e rótulos com grades diferentes")
    gray = to_gray(image_data)
    columns, rows, slices = gray.shape
    out = np.empty((slices, rows, columns, 4), dtype=np.uint8)
    out[..., 3] = 255
    for k in range(slices):
        out[k, :, :, :3] = blend(gray[:, :, k].T, labels[:, :, k].T)
    return out


def _display(plane: np.ndarray) -> np.ndarray:
    """Plano de um volume em orientação RAS para a tela, na convenção radiológica.

    Axial e coronal: direita do paciente à esquerda da tela. Sagital: anterior à
    esquerda. Em todos, superior (ou anterior, no axial) em cima.
    """
    return np.swapaxes(plane[::-1, ::-1], 0, 1)


def _extent(labels: np.ndarray, wanted, axis: int) -> tuple[int, int] | None:
    mask = np.isin(labels, wanted)
    if not mask.any():
        return None
    other = tuple(i for i in range(3) if i != axis)
    present = np.flatnonzero(mask.any(axis=other))
    return int(present[0]), int(present[-1])


def _positions(extent: tuple[int, int] | None, size: int, count: int) -> list[int]:
    if extent is None:
        extent = (int(size * 0.35), int(size * 0.65))
    low, high = extent
    return [int(round(low + (high - low) * (i + 1) / (count + 1))) for i in range(count)]


def choose_slices(labels: np.ndarray) -> dict[str, list[int]]:
    """Cortes da página de conferência, em índices do volume em orientação RAS."""
    hippocampi = (HIPPOCAMPUS_LEFT, HIPPOCAMPUS_RIGHT)
    coronal = _positions(_extent(labels, hippocampi, 1), labels.shape[1], 4)
    low = _extent(labels, hippocampi, 2)
    high = _extent(labels, LATERAL_VENTRICLES, 2)
    span = (low[0], high[1]) if low and high and high[1] > low[0] else None
    axial = _positions(span, labels.shape[2], 4)
    sagittal = []
    for wanted in ((HIPPOCAMPUS_RIGHT,), (THALAMUS_RIGHT,), (THALAMUS_LEFT,), (HIPPOCAMPUS_LEFT,)):
        extent = _extent(labels, wanted, 0)
        sagittal.append((extent[0] + extent[1]) // 2 if extent else labels.shape[0] // 2)
    return {"axial": axial, "coronal": coronal, "sagital": sagittal}


def _crop_bounds(labels: np.ndarray, margin: int = 6) -> tuple[slice, slice, slice]:
    occupied = np.argwhere(labels > 0)
    if occupied.size == 0:
        return (slice(None),) * 3
    low = np.maximum(occupied.min(0) - margin, 0)
    high = np.minimum(occupied.max(0) + margin + 1, labels.shape)
    return tuple(slice(int(l), int(h)) for l, h in zip(low, high))  # type: ignore[return-value]


def montage_figure(image, labels: np.ndarray, title_line: str = ""):
    """Página de conferência: 4 cortes axiais, 4 coronais e 4 sagitais com as cores."""
    labels_image = nib.Nifti1Image(np.asarray(labels, dtype=np.int16), image.affine)
    canonical = nib.as_closest_canonical(image)
    canonical_labels = np.asarray(nib.as_closest_canonical(labels_image).dataobj)
    bounds = _crop_bounds(canonical_labels)
    gray = to_gray(np.asarray(canonical.dataobj))[bounds]
    lab = canonical_labels[bounds]
    dx, dy, dz = (float(z) for z in canonical.header.get_zooms()[:3])
    chosen = choose_slices(lab)

    # Letras brancas com contorno preto: legíveis sobre tecido claro ou escuro.
    outlined = [patheffects.withStroke(linewidth=2.0, foreground="black")]
    fig = plt.figure(figsize=(8.27, 11.69), facecolor=SURFACE)
    left, right = 0.08, 0.92
    draw_page_title(fig, "Conferência da segmentação", left, right)
    if title_line:
        fig.text(left, 0.925, title_line, fontsize=9.5, color=INK, va="top")
    fig.text(left, 0.906, "As cores mostram o que foi medido. Confira se cada estrutura está no lugar e do lado certo.",
             fontsize=8.5, color=INK_SECONDARY, va="top")

    grid = fig.add_gridspec(3, 4, left=left, right=right, top=0.875, bottom=0.17, wspace=0.04, hspace=0.10)
    rows = [("axial", lambda k: (gray[:, :, k], lab[:, :, k]), dy / dx, True),
            ("coronal", lambda j: (gray[:, j, :], lab[:, j, :]), dz / dx, True),
            ("sagital", lambda i: (gray[i, :, :], lab[i, :, :]), dz / dy, False)]
    for row, (name, cut, aspect, sided) in enumerate(rows):
        for column, position in enumerate(chosen[name]):
            ax = fig.add_subplot(grid[row, column])
            g, l = cut(position)
            ax.imshow(blend(_display(g), _display(l)), aspect=aspect, interpolation="nearest")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_facecolor("black")
            if column == 0:
                ax.set_ylabel(name, fontsize=8, color=INK_SECONDARY)
            if sided:
                ax.text(0.03, 0.5, "D", transform=ax.transAxes, color="white", fontsize=9, fontweight="bold", va="center",
                        path_effects=outlined)
                ax.text(0.97, 0.5, "E", transform=ax.transAxes, color="white", fontsize=9, fontweight="bold", va="center",
                        ha="right", path_effects=outlined)
            else:
                ax.text(0.03, 0.04, SAGITTAL_CAPTIONS[column], transform=ax.transAxes, color="white", fontsize=7,
                        path_effects=outlined)

    handles = [Patch(facecolor=tuple(c / 255 for c in LABEL_STYLE[label][:3]), edgecolor="#898781", linewidth=0.4, label=text)
               for label, text in LEGEND]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(left - 0.008, 0.155), ncol=5, frameon=False, fontsize=7.5,
               labelcolor=INK_SECONDARY, handlelength=1.2, columnspacing=1.4)
    fig.text(left, 0.095, "D = direita do paciente, E = esquerda. Axial e coronal na convenção radiológica "
             "(direita do paciente à esquerda da imagem).", fontsize=7.5, color=INK_SECONDARY, va="top")
    fig.text(left, 0.045, DISCLAIMER, fontsize=7.5, color=INK, va="top", fontweight="bold")
    return fig
