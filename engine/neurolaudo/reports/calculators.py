"""Calculadoras clínicas de neurorradiologia."""
from __future__ import annotations

# Regiões do ASPECTS (território da ACM)
ASPECTS_REGIONS: list[tuple[str, str]] = [
    ("C", "Caudado"),
    ("L", "Núcleo lentiforme"),
    ("IC", "Cápsula interna"),
    ("I", "Ínsula"),
    ("M1", "Córtex anterior da ACM"),
    ("M2", "Córtex lateral à ínsula"),
    ("M3", "Córtex posterior da ACM"),
    ("M4", "Córtex anterior (supraganglionar)"),
    ("M5", "Córtex lateral (supraganglionar)"),
    ("M6", "Córtex posterior (supraganglionar)"),
]


def aspects_score(affected: set[str]) -> int:
    """ASPECTS = 10 menos 1 ponto por região acometida."""
    valid = {code for code, _ in ASPECTS_REGIONS}
    unknown = affected - valid
    if unknown:
        raise ValueError(f"Regiões inválidas: {sorted(unknown)}")
    return 10 - len(affected)


def abc2_volume(a_cm: float, b_cm: float, c_cm: float) -> float:
    """Volume de hematoma intraparenquimatoso pelo método ABC/2 (em mL = cm³).

    A = maior diâmetro axial, B = diâmetro perpendicular a A no mesmo corte,
    C = extensão craniocaudal (nº de cortes com hematoma × espessura).
    """
    if min(a_cm, b_cm, c_cm) < 0:
        raise ValueError("Medidas não podem ser negativas")
    return a_cm * b_cm * c_cm / 2.0


def evans_index(frontal_horns_mm: float, inner_skull_mm: float) -> float:
    """Índice de Evans (> 0,3 sugere ventriculomegalia)."""
    if inner_skull_mm <= 0:
        raise ValueError("Diâmetro do crânio deve ser positivo")
    return frontal_horns_mm / inner_skull_mm
