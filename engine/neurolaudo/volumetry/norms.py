"""Compara volumes cerebrais com uma referência de adultos saudáveis.

Modelo e parâmetros do Neurodesk (ver data/AVISO-NORMAS.md). Para cada
estrutura e sexo, com a = (idade - 50) / 10:

    ln V = b0 + b1*a + b2*a^2 + c*ln(ICV / 1500 mL) + erro,  erro ~ Normal(0, sigma(a)^2)
    ln sigma(a) = g0 + g1*a

Avaliação de um paciente:

    y = ln V - c*ln(ICV / 1500 mL)          (volume ajustado ao tamanho da cabeça)
    z = (y - (b0 + b1*a + b2*a^2)) / sigma(a)
    percentil = 100 * Phi(z)

Uso em pesquisa. Não validado para diagnóstico.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Mapping

DEFAULT_NORMS = Path(__file__).parent / "data" / "brainquant_norms.json"
LOW_PERCENTILE = 5.0
HIGH_PERCENTILE = 95.0
_NORMAL = NormalDist()

# Nomes das estruturas para o relatório.
TITLES_PT = {
    "hippocampus_left": "Hipocampo esquerdo",
    "hippocampus_right": "Hipocampo direito",
    "amygdala_left": "Amígdala esquerda",
    "amygdala_right": "Amígdala direita",
    "thalamus_left": "Tálamo esquerdo",
    "thalamus_right": "Tálamo direito",
    "lateral_ventricles": "Ventrículos laterais",
    "cortical_grey_matter": "Córtex cerebral",
    "cerebral_white_matter": "Substância branca cerebral",
    "whole_brain": "Encéfalo (parênquima)",
}


@dataclass(frozen=True)
class NormModel:
    """Modelo do log do volume (mm³) no ICV de referência, em idade escalada `a`."""

    mu: tuple[float, float, float]
    icv_slope: float
    log_sigma: tuple[float, float]

    def location(self, a: float) -> float:
        b0, b1, b2 = self.mu
        return b0 + b1 * a + b2 * a * a

    def scale(self, a: float) -> float:
        g0, g1 = self.log_sigma
        return math.exp(g0 + g1 * a)

    def z(self, a: float, adjusted_log_volume: float) -> float:
        return (adjusted_log_volume - self.location(a)) / self.scale(a)

    def centile_mm3(self, a: float, quantile: float) -> float:
        """Volume (mm³) no ICV de referência para um quantil entre 0 e 1."""
        return math.exp(self.location(a) + _NORMAL.inv_cdf(quantile) * self.scale(a))


@dataclass(frozen=True)
class Structure:
    id: str
    title: str
    columns: tuple[str, ...]
    models: Mapping[str, NormModel]


@dataclass(frozen=True)
class Norms:
    structures: tuple[Structure, ...]
    age_center: float
    age_scale: float
    icv_column: str
    reference_icv_mm3: float
    age_min: float
    age_max: float
    description: str

    def scaled_age(self, age: float) -> float:
        return (age - self.age_center) / self.age_scale

    def structure(self, structure_id: str) -> Structure:
        for s in self.structures:
            if s.id == structure_id:
                return s
        raise KeyError(structure_id)


@dataclass(frozen=True)
class StructureResult:
    structure: Structure
    volume_mm3: float
    adjusted_mm3: float
    z: float | None

    @property
    def volume_ml(self) -> float:
        return self.volume_mm3 / 1000.0

    @property
    def percentile(self) -> float | None:
        return None if self.z is None else 100.0 * _NORMAL.cdf(self.z)

    @property
    def flag(self) -> str:
        p = self.percentile
        if p is None:
            return ""
        if p < LOW_PERCENTILE:
            return "abaixo do percentil 5"
        if p > HIGH_PERCENTILE:
            return "acima do percentil 95"
        return ""


@dataclass(frozen=True)
class Assessment:
    norms: Norms
    icv_mm3: float
    age: float | None
    model_key: str
    results: tuple[StructureResult, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def result(self, structure_id: str) -> StructureResult:
        for r in self.results:
            if r.structure.id == structure_id:
                return r
        raise KeyError(structure_id)


def load_norms(path: str | Path | None = None) -> Norms:
    raw = json.loads(Path(path or DEFAULT_NORMS).read_text(encoding="utf-8"))
    structures = []
    for item in raw["structures"]:
        models = {
            key: NormModel(mu=tuple(m["mu"]), icv_slope=float(m["icv_slope"]), log_sigma=tuple(m["log_sigma"]))
            for key, m in item["models"].items()
        }
        structures.append(Structure(id=item["id"], title=TITLES_PT.get(item["id"], item["title"]),
                                    columns=tuple(item["columns"]), models=models))
    ref = raw["reference"]
    return Norms(structures=tuple(structures), age_center=float(raw["age_center"]), age_scale=float(raw["age_scale"]),
                 icv_column=raw["icv_column"], reference_icv_mm3=float(raw["reference_icv_mm3"]),
                 age_min=float(ref["age_min"]), age_max=float(ref["age_max"]),
                 description=f"{ref['subjects']} adultos saudáveis ({ref['cohort']}), {ref['synthseg']}")


def model_key_for(sex: str | None) -> str:
    """'female', 'male' ou 'all' (sexo desconhecido), a partir do sexo do DICOM ou por extenso."""
    s = (sex or "").strip().lower()
    if s in ("f", "female", "feminino", "mulher"):
        return "female"
    if s in ("m", "male", "masculino", "homem"):
        return "male"
    return "all"


def assess(norms: Norms, volumes: Mapping[str, float], age: float | None, sex: str | None) -> Assessment:
    """Avalia os volumes (mm³, colunas do CSV do SynthSeg) contra a referência."""
    if norms.icv_column not in volumes:
        raise ValueError(f"faltou a coluna '{norms.icv_column}' (volume intracraniano total)")
    icv = float(volumes[norms.icv_column])
    if not icv > 0:
        raise ValueError("volume intracraniano total inválido")
    key = model_key_for(sex)
    warnings: list[str] = []
    if key == "all":
        warnings.append("Sexo desconhecido: usada a referência de mulheres e homens juntos.")
    if age is None:
        warnings.append("Idade desconhecida: sem percentis.")
    elif not norms.age_min <= age <= norms.age_max:
        warnings.append(f"Idade fora da faixa da referência ({norms.age_min:.0f} a {norms.age_max:.0f} anos): "
                        "percentis extrapolados.")

    results = []
    for structure in norms.structures:
        missing = [c for c in structure.columns if c not in volumes]
        if missing:
            raise ValueError(f"faltam colunas para {structure.title}: {', '.join(missing)}")
        volume = float(sum(volumes[c] for c in structure.columns))
        model = structure.models[key]
        if volume > 0:
            adjusted_log = math.log(volume) - model.icv_slope * math.log(icv / norms.reference_icv_mm3)
            adjusted = math.exp(adjusted_log)
            z = None if age is None else model.z(norms.scaled_age(age), adjusted_log)
        else:
            adjusted, z = 0.0, None
            warnings.append(f"{structure.title}: volume zero, sem percentil.")
        results.append(StructureResult(structure=structure, volume_mm3=volume, adjusted_mm3=adjusted, z=z))
    return Assessment(norms=norms, icv_mm3=icv, age=age, model_key=key, results=tuple(results), warnings=tuple(warnings))


def asymmetry_percent(left_mm3: float, right_mm3: float) -> float:
    """Índice de assimetria, em %: (esquerdo - direito) / média. Positivo = esquerdo maior."""
    mean = (left_mm3 + right_mm3) / 2.0
    if not mean > 0:
        raise ValueError("volumes inválidos para assimetria")
    return 100.0 * (left_mm3 - right_mm3) / mean
