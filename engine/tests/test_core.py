import numpy as np
import pytest

import make_phantom
from neurolaudo.dicom.loader import load_volume, scan_folder
from neurolaudo.imaging.mpr import Plane, from_voxel, get_slice, pixel_spacing, to_voxel
from neurolaudo.imaging.windowing import apply_window
from neurolaudo.reports.calculators import abc2_volume, aspects_score, evans_index
from neurolaudo.reports.templates import TEMPLATES, render_text


@pytest.fixture(scope="module")
def volume(tmp_path_factory):
    out = tmp_path_factory.mktemp("phantom")
    make_phantom.write(str(out), nz=20, ny=64, nx=64)
    series = scan_folder(str(out))
    assert len(series) == 1
    return load_volume(series[0])


def test_volume_sorted_and_scaled(volume):
    assert volume.data.shape == (20, 64, 64)
    assert volume.spacing == pytest.approx((2.5, 0.8, 0.8))
    ref = make_phantom.phantom(20, 64, 64)
    # arquivos foram gravados fora de ordem: o loader deve reordenar por posição
    np.testing.assert_allclose(volume.data, (ref + 1024).astype(np.int16) - 1024, atol=1)
    assert volume.default_window == (40.0, 80.0)
    assert volume.series.patient_name == "FANTOMA TESTE"


def test_mpr_shapes_and_orientation():
    vol = np.zeros((10, 20, 30), np.float32)
    vol[9] = 1  # corte mais superior
    assert get_slice(vol, Plane.AXIAL, 0).shape == (20, 30)
    cor = get_slice(vol, Plane.CORONAL, 5)
    sag = get_slice(vol, Plane.SAGITTAL, 5)
    assert cor.shape == (10, 30) and sag.shape == (10, 20)
    assert cor[0].all() and not cor[-1].any()  # superior em cima
    assert pixel_spacing((5, 1, 2), Plane.CORONAL) == (5, 2)


def test_slab_projections():
    vol = np.zeros((5, 4, 4), np.float32)
    vol[1, 0, 0], vol[3, 0, 0] = 10, -10
    assert get_slice(vol, Plane.AXIAL, 2, thickness=5, mode="mip")[0, 0] == 10
    assert get_slice(vol, Plane.AXIAL, 2, thickness=5, mode="minip")[0, 0] == -10
    assert get_slice(vol, Plane.AXIAL, 2, thickness=5, mode="avg")[0, 0] == 0


@pytest.mark.parametrize("plane", list(Plane))
def test_voxel_roundtrip(plane):
    shape = (10, 20, 30)
    vox = to_voxel(plane, 4, 3, 7, shape)
    assert from_voxel(plane, vox) == 4


def test_window():
    out = apply_window(np.array([0, 40, 80, 1000], np.float32), 40, 80)
    assert out.tolist() == [0, 127, 255, 255]


def test_calculators():
    assert aspects_score(set()) == 10
    assert aspects_score({"C", "M2"}) == 8
    with pytest.raises(ValueError):
        aspects_score({"X"})
    assert abc2_volume(4, 3, 2) == 12
    assert evans_index(36, 120) == pytest.approx(0.3)


def test_templates_render():
    for t in TEMPLATES:
        text = render_text(t)
        assert text.startswith(t.title)
        assert "IMPRESSÃO:" in text
    avc = next(t for t in TEMPLATES if t.key == "tc_avc")
    assert "ASPECTS: 9" in render_text(avc, {"aspects": "9"})
