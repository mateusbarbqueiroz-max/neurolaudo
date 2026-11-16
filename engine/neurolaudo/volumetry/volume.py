"""Volumes NIfTI: leitura, recorte em volta da cabeça e volta à grade original.

O recorte só tira voxels: não mexe nas intensidades nem na grade.
"""
from __future__ import annotations

from dataclasses import dataclass

import nibabel as nib
import numpy as np


class VolumeError(ValueError):
    """Volume que não serve para a volumetria; a mensagem vai para o usuário."""


@dataclass(frozen=True)
class Box:
    """Caixa de recorte em índices de voxel: `low` incluso, `high` excluso."""

    low: tuple[int, int, int]
    high: tuple[int, int, int]

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(h - l for l, h in zip(self.low, self.high))  # type: ignore[return-value]

    @property
    def slices(self) -> tuple[slice, slice, slice]:
        return tuple(slice(l, h) for l, h in zip(self.low, self.high))  # type: ignore[return-value]


def load_image(path: str) -> nib.Nifti1Image:
    """Lê um volume 3D. Um 4D com um único volume é aceito."""
    try:
        image = nib.load(path)
    except Exception as error:  # nibabel levanta tipos variados para arquivo ruim
        raise VolumeError(f"não foi possível ler o volume {path}: {error}") from error
    shape = image.shape
    if len(shape) == 4 and shape[3] == 1:
        image = image.slicer[:, :, :, 0]
    elif len(shape) != 3:
        raise VolumeError(f"o volume precisa ter 3 dimensões; este tem {len(shape)}")
    if min(image.shape) < 16:
        raise VolumeError(f"volume pequeno demais para volumetria: {image.shape[0]} x {image.shape[1]} x {image.shape[2]} voxels")
    return image


def voxel_sizes(image) -> tuple[float, float, float]:
    return tuple(float(z) for z in image.header.get_zooms()[:3])  # type: ignore[return-value]


def orientation(image) -> str:
    """Direção em que cada índice cresce, em letras: R/L, A/P, S/I (por exemplo 'LPS')."""
    return "".join(nib.aff2axcodes(image.affine))


def paste_labels(full_shape, box: Box, trimmed_labels: np.ndarray) -> np.ndarray:
    """Rótulos da imagem recortada de volta à grade original; fora da caixa fica 0."""
    if tuple(trimmed_labels.shape[:3]) != box.shape:
        raise VolumeError(f"a segmentação ({trimmed_labels.shape}) não tem a grade da imagem recortada ({box.shape})")
    full = np.zeros(tuple(full_shape[:3]), dtype=np.int16)
    full[box.slices] = np.asarray(trimmed_labels).astype(np.int16)
    return full


# --- Caixa da cabeça -------------------------------------------------------------------------
#
# As normas foram ajustadas recortando cada imagem em volta do encéfalo com o SynthStrip. Esse
# programa roda em PyTorch, que em Mac com Apple Silicon faz as convoluções 3D por um caminho que
# pede dezenas de GB (no servidor Mac de teste, nem um recorte de 12 cm terminou em 20 minutos).
# No lugar dele, o motor acha a cabeça direto na imagem: o topo do couro cabeludo e os 18 cm
# abaixo dele, como faz o `robustfov` do FSL. A caixa fica um pouco maior que a das normas
# (inclui orelhas e nariz); o efeito nos volumes é medido por scripts/validate_ixi.py.

HEAD_HEIGHT_MM = 180.0       # do topo da cabeça para baixo: encéfalo, cerebelo e folga
HEAD_MARGIN_MM = 5.0         # folga em volta da cabeça
_COARSE_MM = 4.0             # a cabeça é procurada em blocos de cerca de 4 mm, para o ruído não atrapalhar


def _block_mean(data: np.ndarray, factors) -> np.ndarray:
    """Média em blocos de `factors` voxels (o resto que não fecha um bloco é descartado)."""
    shape = [n // f for n, f in zip(data.shape, factors)]
    cut = data[: shape[0] * factors[0], : shape[1] * factors[1], : shape[2] * factors[2]]
    return cut.reshape(shape[0], factors[0], shape[1], factors[1], shape[2], factors[2]).mean(axis=(1, 3, 5))


def _otsu(values: np.ndarray) -> float:
    """Limiar de Otsu: separa o ar (escuro) do que é cabeça (claro)."""
    high = float(np.percentile(values, 99.5))
    low = float(values.min())
    if not high > low:
        raise VolumeError("a imagem não tem contraste: não encontrei a cabeça")
    histogram, edges = np.histogram(np.clip(values, low, high), bins=128, range=(low, high))
    centres = (edges[:-1] + edges[1:]) / 2
    weight = histogram.astype(float)
    below = np.cumsum(weight)
    above = below[-1] - below
    sum_below = np.cumsum(weight * centres)
    mean_below = np.divide(sum_below, below, out=np.zeros_like(sum_below), where=below > 0)
    mean_above = np.divide(sum_below[-1] - sum_below, above, out=np.zeros_like(sum_below), where=above > 0)
    between = below * above * (mean_below - mean_above) ** 2
    return float(centres[int(np.argmax(between))])


def _bounds(counts: np.ndarray, minimum: int) -> tuple[int, int]:
    present = np.flatnonzero(counts >= minimum)
    return int(present[0]), int(present[-1])


def head_box(image, height_mm: float = HEAD_HEIGHT_MM, margin_mm: float = HEAD_MARGIN_MM) -> Box:
    """Caixa da cabeça: do topo do couro cabeludo até `height_mm` abaixo, com a largura e o comprimento da cabeça."""
    data = np.asarray(image.dataobj, dtype=np.float32)
    zooms = voxel_sizes(image)
    codes = nib.aff2axcodes(image.affine)
    factors = [max(1, int(round(_COARSE_MM / z))) for z in zooms]
    coarse = _block_mean(data, factors)
    if min(coarse.shape) < 4:
        raise VolumeError("volume pequeno demais para localizar a cabeça")
    # Metade do limiar de Otsu: prefere incluir um pouco de ar a deixar pele de fora.
    head = coarse > 0.5 * _otsu(coarse)

    vertical = next(axis for axis, code in enumerate(codes) if code in ("S", "I"))
    upward = codes[vertical] == "S"                       # o índice cresce para cima?
    step_mm = zooms[vertical] * factors[vertical]
    others = tuple(axis for axis in range(3) if axis != vertical)
    per_slice = head.sum(axis=others)
    if not upward:
        per_slice = per_slice[::-1]                       # agora o índice 0 é o corte mais baixo
    # Topo: o corte mais alto com cabeça de verdade (uns 2 cm² ou mais) seguido de cortes também com cabeça.
    solid = per_slice >= 12
    top = None
    for index in range(len(per_slice) - 1, -1, -1):
        if solid[index] and solid[max(index - 2, 0): index + 1].all():
            top = index
            break
    if top is None:
        raise VolumeError("não encontrei a cabeça na imagem")
    bottom = max(0, top - int(round(height_mm / step_mm)) + 1)

    # Largura e comprimento: a cabeça dentro dessa faixa, sem contar pontos soltos.
    slab_index = [slice(None)] * 3
    if upward:
        slab_index[vertical] = slice(bottom, top + 1)
    else:
        size = head.shape[vertical]
        slab_index[vertical] = slice(size - 1 - top, size - bottom)
    slab = head[tuple(slab_index)]
    low, high = [0, 0, 0], [0, 0, 0]
    for axis in others:
        rest = tuple(a for a in range(3) if a != axis)
        first, last = _bounds(slab.sum(axis=rest), 3)
        low[axis], high[axis] = first * factors[axis], (last + 1) * factors[axis]
    span = slab_index[vertical]
    low[vertical], high[vertical] = span.start * factors[vertical], span.stop * factors[vertical]

    margins = [int(np.ceil(margin_mm / z)) for z in zooms]
    low = [max(0, l - m) for l, m in zip(low, margins)]
    high = [min(n, h + m) for h, m, n in zip(high, margins, data.shape[:3])]
    # Para baixo não há folga a dar: a faixa já termina em tecido (pescoço), e a altura é o que vale.
    if upward:
        low[vertical] = max(0, span.start * factors[vertical])
    else:
        high[vertical] = min(data.shape[vertical], span.stop * factors[vertical])
    return Box(tuple(int(v) for v in low), tuple(int(v) for v in high))


def trim_to_head(image, height_mm: float = HEAD_HEIGHT_MM, margin_mm: float = HEAD_MARGIN_MM):
    """Recorta a imagem na caixa da cabeça. Devolve (imagem recortada, caixa)."""
    box = head_box(image, height_mm, margin_mm)
    a, b, c = box.slices
    return image.slicer[a, b, c], box
