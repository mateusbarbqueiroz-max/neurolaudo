"""Reconstrução multiplanar (MPR) e projeções (MIP/MinIP) a partir do volume axial."""
from __future__ import annotations

from enum import Enum

import numpy as np


class Plane(str, Enum):
    AXIAL = "Axial"
    CORONAL = "Coronal"
    SAGITTAL = "Sagital"


def n_slices(shape: tuple[int, int, int], plane: Plane) -> int:
    z, y, x = shape
    return {Plane.AXIAL: z, Plane.CORONAL: y, Plane.SAGITTAL: x}[plane]


def get_slice(vol: np.ndarray, plane: Plane, index: int, thickness: int = 1,
              mode: str = "avg") -> np.ndarray:
    """Retorna o corte 2D (linhas, colunas) já orientado para exibição.

    thickness > 1 gera um slab (média, MIP ou MinIP) centrado no índice.
    Coronal/sagital são invertidos verticalmente para que o crânio fique em cima.
    """
    n = n_slices(vol.shape, plane)
    index = int(np.clip(index, 0, n - 1))
    half = max(thickness, 1) // 2
    lo, hi = max(index - half, 0), min(index + half + 1, n)

    if plane == Plane.AXIAL:
        slab = vol[lo:hi]
        axis = 0
    elif plane == Plane.CORONAL:
        slab = vol[:, lo:hi, :]
        axis = 1
    else:
        slab = vol[:, :, lo:hi]
        axis = 2

    if mode == "mip":
        img = slab.max(axis=axis)
    elif mode == "minip":
        img = slab.min(axis=axis)
    else:
        img = slab.mean(axis=axis)

    if plane != Plane.AXIAL:
        img = img[::-1]
    return np.ascontiguousarray(img)


def pixel_spacing(spacing: tuple[float, float, float], plane: Plane) -> tuple[float, float]:
    """(espaçamento entre linhas, entre colunas) em mm para o plano exibido."""
    sz, sy, sx = spacing
    return {Plane.AXIAL: (sy, sx), Plane.CORONAL: (sz, sx), Plane.SAGITTAL: (sz, sy)}[plane]


def to_voxel(plane: Plane, index: int, row: float, col: float,
             shape: tuple[int, int, int]) -> tuple[int, int, int]:
    """Converte (índice do corte, linha, coluna) exibidos em coordenada de voxel (z, y, x)."""
    z, _y, _x = shape
    if plane == Plane.AXIAL:
        return index, int(row), int(col)
    if plane == Plane.CORONAL:
        return z - 1 - int(row), index, int(col)
    return z - 1 - int(row), int(col), index


def from_voxel(plane: Plane, voxel: tuple[int, int, int]) -> int:
    """Índice do corte, no plano dado, que contém o voxel."""
    vz, vy, vx = voxel
    return {Plane.AXIAL: vz, Plane.CORONAL: vy, Plane.SAGITTAL: vx}[plane]
