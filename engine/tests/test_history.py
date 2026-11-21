"""Histórico deste Mac e comparação com o exame anterior."""
import json
import stat

import pytest

from neurolaudo.volumetry import history, pipeline
from neurolaudo.volumetry.norms import assess, load_norms
from neurolaudo.volumetry.report import ReportHeader
from neurolaudo.volumetry.tables import read_volumes_csv
from test_pipeline import IXI_CSV, SUBJECT, fake_tools, make_t1  # noqa: F401  (fake_tools é usado como fixture)

NORMS = load_norms()


def assessment(scale=None, age=70.0, sex="F"):
    volumes = dict(read_volumes_csv(IXI_CSV, SUBJECT))
    for column, factor in (scale or {}).items():
        volumes[column] *= factor
    return assess(NORMS, volumes, age=age, sex=sex)


def record(secret, exam="1.2.3.4", date="20250310", age=70.0, scale=None, voxel=(1.0, 1.0, 1.0), tr=2300.0, patient="PAC-77"):
    tracking = {"id": patient, "exame": exam, "data": date, "serie": "T1 3D", "aquisicao": {"tr": tr, "te": 2.98}}
    return history.make_record(assessment(scale, age), tracking, (176, 256, 256), voxel, secret)


def hippocampus_columns():
    return NORMS.structure("hippocampus_left").columns


def limits(value):
    table = {s.id: {"mesmo_aparelho": {"limite_pct": value}, "aparelhos_diferentes": {"limite_pct": 2 * value}}
             for s in NORMS.structures}
    return {"medida": "ajustado", "pessoas": 20, "fonte": "teste", "variantes": {"ajustado": table}}


def test_secret_is_created_once_and_private(tmp_path):
    folder = tmp_path / "historico"
    first = history.load_secret(folder)
    assert len(first) == 32 and history.load_secret(folder) == first
    assert stat.S_IMODE((folder / history.KEY_FILE).stat().st_mode) == 0o600


def test_record_keeps_no_identifiers(tmp_path):
    secret = history.load_secret(tmp_path)
    r = record(secret)
    text = json.dumps(r)
    assert "PAC-77" not in text and "1.2.3.4" not in text
    assert len(r["paciente"]) == 64 and r["paciente"] == record(secret)["paciente"]
    assert r["paciente"] != record(history.load_secret(tmp_path / "outro"))["paciente"]
    assert r["data"] == "20250310" and r["sexo"] == "female" and r["aquisicao"]["tr_ms"] == 2300.0
    assert history.make_record(assessment(), {"id": "", "exame": "x", "data": "20250310"}, (1, 1, 1), (1, 1, 1), secret) is None


def test_earlier_exams_of_the_same_patient_only(tmp_path):
    secret = history.load_secret(tmp_path)
    current = record(secret, exam="atual", date="20261110", age=71.7)
    history.save(tmp_path, record(secret, exam="antigo", date="20250310", age=70.0))
    history.save(tmp_path, record(secret, exam="atual", date="20261110", age=71.7))         # o próprio exame
    history.save(tmp_path, record(secret, exam="depois", date="20270101", age=71.8))        # posterior
    history.save(tmp_path, record(secret, exam="outro", date="20240101", patient="PAC-78"))  # outro paciente
    history.save(tmp_path, record(secret, exam="estranho", date="20240101", age=40.0))      # idade não fecha
    found, notes = history.earlier_exams(tmp_path, current)
    assert [r["exame"] for r in found] == [history.scramble(secret, "exame", "antigo")]
    assert len(notes) == 1 and "não" in notes[0]
    assert stat.S_IMODE(next(tmp_path.glob("*.json")).stat().st_mode) == 0o600


def test_comparison_marks_only_what_passes_the_repeat_limit(tmp_path):
    secret = history.load_secret(tmp_path)
    prior = record(secret, exam="a", date="20250310", age=70.0)
    shrink = {c: 0.94 for c in hippocampus_columns()}
    current = record(secret, exam="b", date="20261110", age=71.7, scale=shrink)
    comparison = history.compare(NORMS, prior, current, limits(3.0))
    rows = {r["id"]: r for r in comparison["estruturas"]}
    assert comparison["cenario"] == "mesmo_aparelho" and comparison["intervalo"] == "1 ano e 8 meses"
    assert rows["hippocampus_left"]["variacao_pct"] == -6.0 and rows["hippocampus_left"]["marca"] == "redução"
    assert rows["hippocampus_left"]["por_ano_pct"] == pytest.approx(-3.6, abs=0.1)
    assert rows["hippocampus_right"]["marca"] == "" and rows["lateral_ventricles"]["variacao_pct"] == 0.0
    assert comparison["frase"] == ("Comparação com o exame de 10/03/2025 (1 ano e 8 meses): variação além do esperado só "
                                   "pela repetição do exame em hipocampo esquerdo (-6,0 %; esperado até ±3,0 %).")


def test_different_acquisition_uses_the_wider_limit(tmp_path):
    secret = history.load_secret(tmp_path)
    prior = record(secret, exam="a", date="20250310", voxel=(0.9, 0.9, 1.2))
    current = record(secret, exam="b", date="20250410", age=70.1, scale={c: 0.95 for c in hippocampus_columns()})
    comparison = history.compare(NORMS, prior, current, limits(3.0))
    left = next(r for r in comparison["estruturas"] if r["id"] == "hippocampus_left")
    assert comparison["cenario"] == "aparelhos_diferentes" and left["limite_pct"] == 6.0 and left["marca"] == ""
    assert left["por_ano_pct"] is None
    assert any("Aquisição diferente" in n for n in comparison["avisos"])
    assert any("menor que 6 meses" in n for n in comparison["avisos"])
    assert "aquisição diferente" in comparison["frase"] and "nenhuma estrutura variou" in comparison["frase"]


def test_without_repeat_data_nothing_is_marked(tmp_path):
    secret = history.load_secret(tmp_path)
    comparison = history.compare(NORMS, record(secret, exam="a"), record(secret, exam="b", date="20260310", age=71.0), None)
    assert all(r["marca"] == "" and r["limite_pct"] is None for r in comparison["estruturas"])
    assert comparison["frase"].endswith("hipocampo esquerdo 0,0 %, hipocampo direito 0,0 % e ventrículos laterais 0,0 %.")
    # Sem TR e TE não se afirma que a aquisição mudou; só que não dá para confirmar que é a mesma.
    unknown = history.compare(NORMS, record(secret, exam="a", tr=None), record(secret, exam="b", date="20260310", age=71.0), None)
    assert unknown["aquisicao"] == "não confirmada" and unknown["cenario"] == "aparelhos_diferentes"
    assert "aquisição diferente" not in unknown["frase"] and any("confirmar" in n for n in unknown["avisos"])


def test_second_exam_gets_the_comparison_page(fake_tools, tmp_path):
    t1 = tmp_path / "t1.nii"
    make_t1(t1)
    folder = tmp_path / "historico"
    base = {"id": "FANTOMA-1", "serie": "T1 3D", "aquisicao": {"tr": 2300, "te": 2.98}}
    first = pipeline.run_exam(str(t1), str(tmp_path / "um"), age=70.0, sex="F", header=ReportHeader(patient_name="Fantoma"),
                              history_dir=str(folder), tracking=base | {"exame": "1.2.1", "data": "20250310"})
    assert first["comparacao"] is None and len(first["paginas"]) == 2
    second = pipeline.run_exam(str(t1), str(tmp_path / "dois"), age=71.7, sex="F", header=ReportHeader(patient_name="Fantoma"),
                               history_dir=str(folder), tracking=base | {"exame": "1.2.2", "data": "20261110"})
    assert second["comparacao"]["anterior"]["data"] == "20250310" and len(second["paginas"]) == 3
    assert (tmp_path / "dois" / "comparacao.png").stat().st_size > 10_000
    assert "Comparação com o exame de 10/03/2025" in second["frase_laudo"]
    assert len(list(folder.glob("*.json"))) == 2
    # Sem identificador o exame não entra no histórico, e o motivo aparece nos avisos.
    third = pipeline.run_exam(str(t1), str(tmp_path / "tres"), age=71.7, sex="F", history_dir=str(folder),
                              tracking={"data": "20261110"})
    assert third["comparacao"] is None and any("histórico" in w for w in third["avisos"])
