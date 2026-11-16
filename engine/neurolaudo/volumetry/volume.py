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
# As normas foram ajustadas recortando cada imagem em volta do encéfalo com o SynthStrip (caixa da
# máscara mais 15 mm). Esse programa roda em PyTorch, que em Mac com Apple Silicon faz as
# convoluções 3D por um caminho que pede dezenas de GB (no servidor Mac de teste, nem um recorte
# de 12 cm terminou em 20 minutos). No lugar dele, o motor estima a mesma caixa direto na imagem:
#
# - de cima para baixo: do topo do couro cabeludo até 18 cm abaixo (como o `robustfov` do FSL);
# - largura e comprimento: os da cabeça na altura da calota, acima das orelhas e do nariz. Ali o
#   contorno da cabeça fica a cerca de 15 mm do encéfalo (liquor, osso e couro cabeludo), que é a
#   margem das normas.
#
# Depois de segmentar, `touching_faces` confere se o encéfalo encostou em alguma face da caixa; se
# encostou, o motor alarga a caixa e segmenta de novo.

HEAD_HEIGHT_MM = 180.0       # do topo da cabeça para baixo: encéfalo, cerebelo e folga
CALVARIUM_MM = (25.0, 100.0)  # faixa abaixo do topo onde se medem a largura e o comprimento
HEAD_MARGIN_MM = 5.0         # folga em volta
GROW_MM = 20.0               # quanto a caixa cresce de cada lado em que o encéfalo encostou
BRAIN_MARGIN_MM = 15.0       # margem das normas em volta do encéfalo
_COARSE_MM = 4.0             # a cabeça é procurada em blocos de cerca de 4 mm, para o ruído não atrapalhar
_SIDE_NAMES = {"R": "direita", "L": "esquerda", "A": "frente", "P": "trás", "S": "topo", "I": "base"}
_OPPOSITE = {"R": "L", "L": "R", "A": "P", "P": "A", "S": "I", "I": "S"}
CSF_LABEL = 24               # liquor fora do encéfalo: chega ao osso e não conta como encostar


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


def _vertical(image) -> tuple[int, bool]:
    """Qual índice do volume anda na vertical do paciente, e se cresce para cima."""
    codes = nib.aff2axcodes(image.affine)
    axis = next(a for a, code in enumerate(codes) if code in ("S", "I"))
    return axis, codes[axis] == "S"


def head_box(image, height_mm: float = HEAD_HEIGHT_MM, margin_mm: float = HEAD_MARGIN_MM) -> Box:
    """Caixa em volta do encéfalo, estimada pelo contorno da cabeça (ver o comentário acima)."""
    data = np.asarray(image.dataobj, dtype=np.float32)
    zooms = voxel_sizes(image)
    factors = [max(1, int(round(_COARSE_MM / z))) for z in zooms]
    coarse = _block_mean(data, factors)
    if min(coarse.shape) < 4:
        raise VolumeError("volume pequeno demais para localizar a cabeça")
    # Metade do limiar de Otsu: prefere incluir um pouco de ar a deixar pele de fora.
    head = coarse > 0.5 * _otsu(coarse)
    vertical, upward = _vertical(image)
    if not upward:
        head = np.flip(head, axis=vertical)               # daqui em diante o índice vertical cresce para cima
    step_mm = zooms[vertical] * factors[vertical]
    others = tuple(axis for axis in range(3) if axis != vertical)

    # Topo: o corte mais alto com cabeça de verdade (uns 2 cm² ou mais) seguido de cortes também com cabeça.
    solid = head.sum(axis=others) >= 12
    top = next((i for i in range(len(solid) - 1, -1, -1) if solid[max(i - 2, 0): i + 1].all()), None)
    if top is None:
        raise VolumeError("não encontrei a cabeça na imagem")
    bottom = max(0, top - int(round(height_mm / step_mm)) + 1)

    def slab(first: int, last: int) -> np.ndarray:
        index = [slice(None)] * 3
        index[vertical] = slice(max(first, 0), last + 1)
        return head[tuple(index)]

    # Largura e comprimento: a cabeça na altura da calota. Se quase não há cabeça nessa faixa (imagem
    # pequena ou cortada), vale a faixa inteira.
    calvarium = slab(top - int(round(CALVARIUM_MM[1] / step_mm)), top - int(round(CALVARIUM_MM[0] / step_mm)))
    region = calvarium if calvarium.sum() >= 200 else slab(bottom, top)
    low, high = [0, 0, 0], [0, 0, 0]
    for axis in others:
        rest = tuple(a for a in range(3) if a != axis)
        present = np.flatnonzero(region.sum(axis=rest) >= 3)
        low[axis], high[axis] = int(present[0]) * factors[axis], (int(present[-1]) + 1) * factors[axis]
    low[vertical], high[vertical] = bottom * factors[vertical], (top + 1) * factors[vertical]
    # Folga em volta e em cima. Embaixo não: a faixa termina no pescoço, e o que vale é a altura.
    margins = [int(np.ceil(margin_mm / z)) for z in zooms]
    for axis in range(3):
        if axis != vertical:
            low[axis] = max(0, low[axis] - margins[axis])
        high[axis] = min(data.shape[axis], high[axis] + margins[axis])
    if not upward:                                        # de volta ao sentido original do índice vertical
        size = data.shape[vertical]
        covered = head.shape[vertical] * factors[vertical]
        base = size if low[vertical] == 0 else covered - low[vertical]
        low[vertical], high[vertical] = max(0, covered - high[vertical]), min(size, base)
    return Box(tuple(int(v) for v in low), tuple(int(v) for v in high))


def trim(image, box: Box):
    """A imagem recortada na caixa (mesmas intensidades, mesma grade)."""
    a, b, c = box.slices
    return image.slicer[a, b, c]


def touching_faces(labels: np.ndarray, image, depth: int = 2) -> list[tuple[int, int]]:
    """Faces da caixa em que o encéfalo segmentado encosta: (índice, lado), lado 0 = começo, 1 = fim.

    A face de baixo não conta: ali o tronco continua na medula. O liquor de fora do encéfalo também não.
    `image` é a imagem recortada, na mesma grade dos rótulos.
    """
    brain = (labels > 0) & (labels != CSF_LABEL)
    vertical, upward = _vertical(image)
    faces = []
    for axis in range(3):
        for side in (0, 1):
            if axis == vertical and side == (0 if upward else 1):
                continue
            index = [slice(None)] * 3
            index[axis] = slice(0, depth) if side == 0 else slice(labels.shape[axis] - depth, None)
            if brain[tuple(index)].any():
                faces.append((axis, side))
    return faces


def face_name(image, face: tuple[int, int]) -> str:
    """Nome do lado do paciente para onde a face olha: direita, esquerda, frente, trás, topo ou base."""
    code = nib.aff2axcodes(image.affine)[face[0]]
    return _SIDE_NAMES[code if face[1] == 1 else _OPPOSITE[code]]


def at_image_edge(box: Box, face: tuple[int, int], shape) -> bool:
    axis, side = face
    return box.low[axis] == 0 if side == 0 else box.high[axis] == shape[axis]


def grow(box: Box, faces, zooms, shape, mm: float = GROW_MM) -> Box:
    """A caixa alargada em `mm` nas faces dadas, sem sair da imagem."""
    low, high = list(box.low), list(box.high)
    for axis, side in faces:
        step = int(np.ceil(mm / zooms[axis]))
        if side == 0:
            low[axis] = max(0, low[axis] - step)
        else:
            high[axis] = min(int(shape[axis]), high[axis] + step)
    return Box(tuple(low), tuple(high))


def brain_box(trimmed_labels: np.ndarray, box: Box, zooms, shape, margin_mm: float = BRAIN_MARGIN_MM) -> Box:
    """Caixa das normas a partir da segmentação: tudo o que foi rotulado (encéfalo e liquor) mais a margem.

    As normas usaram a caixa da máscara do SynthStrip mais 15 mm; o conjunto dos rótulos do SynthSeg
    ocupa praticamente o mesmo espaço (o conteúdo de dentro do crânio).
    """
    occupied = np.argwhere(trimmed_labels > 0)
    if occupied.size == 0:
        raise VolumeError("a segmentação veio vazia: a série não parece ser de crânio")
    margin = np.ceil(margin_mm / np.asarray(zooms[:3], dtype=float)).astype(int)
    low = np.maximum(occupied.min(0) + np.asarray(box.low) - margin, 0)
    high = np.minimum(occupied.max(0) + np.asarray(box.low) + margin + 1, np.asarray(shape[:3]))
    return Box(tuple(int(v) for v in low), tuple(int(v) for v in high))
