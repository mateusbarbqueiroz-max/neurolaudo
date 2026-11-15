"""Janelamento e presets voltados à neurorradiologia."""
from __future__ import annotations

import numpy as np

# (nome, centro, largura) em HU
CT_PRESETS: list[tuple[str, float, float]] = [
    ("Encéfalo", 40, 80),
    ("AVC (substância cinzenta/branca)", 35, 30),
    ("Subdural", 75, 215),
    ("Osso", 600, 2800),
    ("Partes moles / pescoço", 50, 350),
    ("Angio-TC", 200, 700),
    ("Seios da face", 400, 2000),
]


def apply_window(img: np.ndarray, center: float, width: float) -> np.ndarray:
    """Converte imagem em HU/intensidade para uint8 (0-255) conforme janela."""
    width = max(float(width), 1.0)
    lo = center - width / 2.0
    out = (img - lo) * (255.0 / width)
    return np.clip(out, 0, 255).astype(np.uint8)


def auto_window(data: np.ndarray) -> tuple[float, float]:
    """Janela automática por percentis (útil para RM, sem unidade absoluta)."""
    sample = data[:: max(1, data.shape[0] // 8)]
    lo, hi = np.percentile(sample, [1, 99.5])
    return float((lo + hi) / 2), float(max(hi - lo, 1))
