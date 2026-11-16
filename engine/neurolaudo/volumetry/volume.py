"""Volumes NIfTI: leitura, recorte ao redor do encéfalo e volta à grade original.

O recorte repete o passo usado para ajustar as normas (Neurodesk,
`fit_brainquant_norms.py`, licença MIT): caixa da máscara do encéfalo mais
15 mm de margem, sem mexer nas intensidades nem na grade de voxels.
"""
from __future__ import annotations

from dataclasses import dataclass

import nibabel as nib
import numpy as np

TRIM_MARGIN_MM = 15.0


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


def trim_box(mask: np.ndarray, zooms, margin_mm: float = TRIM_MARGIN_MM) -> Box:
    occupied = np.argwhere(mask > 0)
    if occupied.size == 0:
        raise VolumeError("a máscara do encéfalo veio vazia: a série não parece ser de crânio")
    margin = np.ceil(margin_mm / np.asarray(zooms[:3], dtype=float)).astype(int)
    low = np.maximum(occupied.min(0) - margin, 0)
    high = np.minimum(occupied.max(0) + margin + 1, mask.shape[:3])
    return Box(tuple(int(v) for v in low), tuple(int(v) for v in high))


def trim_to_mask(image, mask_image, margin_mm: float = TRIM_MARGIN_MM):
    """Recorta a imagem na caixa da máscara mais a margem. Devolve (imagem recortada, caixa)."""
    if tuple(mask_image.shape[:3]) != tuple(image.shape[:3]):
        raise VolumeError(f"a máscara ({mask_image.shape}) não tem a grade da imagem ({image.shape})")
    box = trim_box(np.asarray(mask_image.dataobj), voxel_sizes(image), margin_mm)
    a, b, c = box.slices
    return image.slicer[a, b, c], box


def paste_labels(full_shape, box: Box, trimmed_labels: np.ndarray) -> np.ndarray:
    """Rótulos da imagem recortada de volta à grade original; fora da caixa fica 0."""
    if tuple(trimmed_labels.shape[:3]) != box.shape:
        raise VolumeError(f"a segmentação ({trimmed_labels.shape}) não tem a grade da imagem recortada ({box.shape})")
    full = np.zeros(tuple(full_shape[:3]), dtype=np.int16)
    full[box.slices] = np.asarray(trimmed_labels).astype(np.int16)
    return full
