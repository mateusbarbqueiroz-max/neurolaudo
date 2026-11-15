import csv
import math
import os
import statistics

import pytest

from neurolaudo.volumetry.norms import assess, asymmetry_percent, load_norms, model_key_for

IXI_CSV = os.path.join(os.path.dirname(__file__), "data", "brainquant_ixi_volumes.csv")


@pytest.fixture(scope="module")
def norms():
    return load_norms()


def _volumes_at_median(norms, age, key, icv):
    """Volumes de um sujeito exatamente na mediana da referência, para um dado ICV."""
    a = norms.scaled_age(age)
    volumes = {norms.icv_column: icv}
    for s in norms.structures:
        if len(s.columns) != 1:
            continue
        m = s.models[key]
        volumes[s.columns[0]] = math.exp(m.location(a) + m.icv_slope * math.log(icv / norms.reference_icv_mm3))
    return volumes


def test_loads_ten_structures(norms):
    assert len(norms.structures) == 10
    assert norms.reference_icv_mm3 == 1_500_000
    assert (norms.age_min, norms.age_max) == (20.0, 86.3)
    assert norms.structure("hippocampus_left").title == "Hipocampo esquerdo"


def test_median_subject_is_percentile_50(norms):
    single = [s for s in norms.structures if len(s.columns) == 1]
    for icv in (1_500_000, 1_250_000, 1_800_000):  # o ajuste pelo tamanho da cabeça não muda o z
        volumes = _volumes_at_median(norms, 70, "female", icv)
        for s in norms.structures:
            for c in s.columns:
                volumes.setdefault(c, 1000.0)
        result = assess(norms, volumes, age=70, sex="F")
        for s in single:
            r = result.result(s.id)
            assert r.z == pytest.approx(0, abs=1e-9)
            assert r.percentile == pytest.approx(50)
            assert r.flag == ""


def test_one_sd_below_and_flags(norms):
    s = norms.structure("hippocampus_left")
    m = s.models["male"]
    a = norms.scaled_age(75)
    volumes = {norms.icv_column: norms.reference_icv_mm3}
    for st in norms.structures:
        for c in st.columns:
            volumes[c] = 1000.0
    volumes["left hippocampus"] = math.exp(m.location(a) - 2 * m.scale(a))
    r = assess(norms, volumes, age=75, sex="M").result("hippocampus_left")
    assert r.z == pytest.approx(-2)
    assert r.percentile == pytest.approx(2.275, abs=0.01)
    assert r.flag == "abaixo do percentil 5"
    assert m.centile_mm3(a, 0.5) == pytest.approx(math.exp(m.location(a)))


def test_sex_and_age_handling(norms):
    assert model_key_for("F") == "female" and model_key_for("masculino") == "male"
    assert model_key_for(None) == "all" and model_key_for("O") == "all"
    volumes = {norms.icv_column: 1_500_000.0}
    for st in norms.structures:
        for c in st.columns:
            volumes[c] = 4000.0
    unknown = assess(norms, volumes, age=None, sex=None)
    assert unknown.model_key == "all"
    assert all(r.z is None and r.percentile is None for r in unknown.results)
    assert any("Idade desconhecida" in w for w in unknown.warnings)
    old = assess(norms, volumes, age=95, sex="F")
    assert any("extrapolados" in w for w in old.warnings)
    with pytest.raises(ValueError):
        assess(norms, {"left hippocampus": 4000.0}, age=60, sex="F")


def test_asymmetry():
    assert asymmetry_percent(4000, 4000) == 0
    assert asymmetry_percent(3000, 4000) == pytest.approx(-28.571, abs=0.01)


def test_reference_cohort_scores_as_expected(norms):
    """Os 561 sujeitos do IXI, avaliados pela própria referência.

    As normas publicadas incluem um efeito por aparelho que não é distribuído;
    sem ele, espera-se z com média perto de 0, desvio perto de 1 e cerca de 90 %
    dos valores entre os percentis 5 e 95.
    """
    with open(IXI_CSV, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if not r["exclude"].strip()]
    assert len(rows) == 561
    zs = {s.id: [] for s in norms.structures}
    for row in rows:
        volumes = {k: float(v) for k, v in row.items() if k not in ("subject", "site", "sex", "age", "exclude")}
        result = assess(norms, volumes, age=float(row["age"]), sex=row["sex"])
        for r in result.results:
            zs[r.structure.id].append(r.z)
    for structure_id, values in zs.items():
        inside = sum(1 for z in values if abs(z) <= 1.6449) / len(values)
        assert abs(statistics.fmean(values)) < 0.15, structure_id
        assert 0.9 < statistics.pstdev(values) < 1.15, structure_id
        assert 0.85 < inside < 0.95, structure_id
