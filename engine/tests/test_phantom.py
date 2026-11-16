"""Os exames de teste de RM usados no servidor Mac: dois estudos do mesmo paciente."""
import make_phantom
from neurolaudo.dicom.loader import load_volume, scan_folder


def test_mr_pair_has_two_studies_of_the_same_patient(tmp_path):
    make_phantom.write_mr_pair(str(tmp_path))
    prior = scan_folder(str(tmp_path / "anterior"))
    current = scan_folder(str(tmp_path / "atual"))
    assert [s.description for s in sorted(current, key=lambda s: s.description)] == sorted(make_phantom.MR_SERIES)
    assert len(prior) == len(current) == 6
    assert {s.modality for s in prior + current} == {"MR"}
    assert {s.patient_id for s in prior + current} == {"000002"}
    assert {s.study_date for s in prior} == {"20260110"}
    assert {s.study_date for s in current} == {"20261115"}
    # Estudos e séries distintos entre os dois exames.
    assert len({s.uid for s in prior + current}) == 12


def test_mr_series_loads_as_a_volume(tmp_path):
    make_phantom.write_mr_study(str(tmp_path), "20261115")
    series = next(s for s in scan_folder(str(tmp_path)) if s.description == "AX FLAIR")
    volume = load_volume(series)
    assert volume.data.shape == (16, 128, 128)
    assert volume.spacing == (10.0, 1.6, 1.6)
    assert volume.data.min() >= 0
