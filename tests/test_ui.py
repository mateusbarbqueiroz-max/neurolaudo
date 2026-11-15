import pytest

pytest.importorskip("PySide6")

import make_phantom
from PySide6.QtWidgets import QApplication

from neurolaudo.imaging.mpr import Plane
from neurolaudo.reports.export import ReportHeader, export_pdf
from neurolaudo.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_open_and_render(app, tmp_path):
    make_phantom.write(str(tmp_path / "dcm"), nz=16, ny=64, nx=64)
    win = MainWindow()
    win.open_folder(str(tmp_path / "dcm"))
    assert win.volume is not None
    win.show()
    for v in win.viewers.values():
        v.grab()  # força paintEvent
    win._sync_cross((8, 32, 32))
    assert win.viewers[Plane.CORONAL].index == 32
    win.close()


def test_pdf_export(app, tmp_path):
    p = tmp_path / "laudo.pdf"
    export_pdf(str(p), ReportHeader(patient_name="Teste"), "TITULO\n\nANÁLISE:\n- Normal.")
    assert p.read_bytes().startswith(b"%PDF")
