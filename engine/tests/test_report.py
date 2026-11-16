import json
import os

import matplotlib.pyplot as plt
import pytest

from neurolaudo.volumetry import cli
from neurolaudo.volumetry.norms import StructureResult, assess, load_norms
from neurolaudo.volumetry.report import (DISCLAIMER, ReportHeader, build_figure, flag_text, percentile_text, render_rgb,
                                         save_pdf)

IXI_CSV = os.path.join(os.path.dirname(__file__), "data", "brainquant_ixi_volumes.csv")


@pytest.fixture(scope="module")
def assessment():
    volumes = cli.read_volumes_csv(IXI_CSV, "IXI002-Guys-0828-T1")
    return assess(load_norms(), volumes, age=35.8, sex="female")


def test_reads_one_subject_from_the_synthseg_table():
    volumes = cli.read_volumes_csv(IXI_CSV, "IXI002-Guys-0828-T1")
    assert volumes["total intracranial"] > 1_000_000
    assert "left hippocampus" in volumes and "site" not in volumes
    assert cli.read_volumes_csv(IXI_CSV, "0") == cli.read_volumes_csv(IXI_CSV)
    with pytest.raises(ValueError):
        cli.read_volumes_csv(IXI_CSV, "sujeito-que-nao-existe")


def test_page_has_a_table_and_one_chart_per_structure(assessment):
    fig = build_figure(assessment, ReportHeader(patient_name="Exemplo"))
    try:
        assert len(fig.axes) == 1 + len(assessment.results)
        texts = " ".join(t.get_text() for t in fig.texts)
        assert "Volumetria cerebral" in texts and DISCLAIMER in texts
        titles = [ax.get_title(loc="left") for ax in fig.axes[1:]]
        assert titles[0] == "Hipocampo E" and "Ventrículos lat." in titles
    finally:
        plt.close(fig)


def test_exam_warnings_are_shown_next_to_the_table(assessment):
    plain = build_figure(assessment, ReportHeader())
    warned = build_figure(assessment, ReportHeader(), notes=["Aviso de teste sobre a série."], footnotes=["Nota de rodapé."])
    try:
        texts = [t.get_text() for t in warned.texts]
        assert "Aviso de teste sobre a série." in texts and "Nota de rodapé." in texts
        # Os gráficos descem para dar lugar ao aviso, sem sair da página.
        top = lambda fig: max(ax.get_position().y1 for ax in fig.axes[1:])
        assert 0.3 < top(warned) < top(plain)
    finally:
        plt.close(plain)
        plt.close(warned)


def test_pdf_and_image_outputs(assessment, tmp_path):
    path = tmp_path / "r.pdf"
    save_pdf(str(path), assessment, ReportHeader())
    assert path.read_bytes().startswith(b"%PDF")
    rgb = render_rgb(assessment, ReportHeader(), dpi=60)
    assert rgb.ndim == 3 and rgb.shape[2] == 3 and rgb.dtype.name == "uint8"
    assert rgb.shape[0] > rgb.shape[1]  # página em pé


def test_percentile_and_flag_wording(assessment):
    structure = assessment.results[0].structure

    def result(z):
        return StructureResult(structure=structure, volume_mm3=4000, adjusted_mm3=4000, z=z)

    assert percentile_text(result(-3)) == "< 1"
    assert percentile_text(result(3)) == "> 99"
    assert percentile_text(result(0)) == "50"
    assert percentile_text(result(None)) == "–"
    assert flag_text(result(-2)) == "▼ abaixo do percentil 5"
    assert flag_text(result(2)) == "▲ acima do percentil 95"
    assert flag_text(result(0)) == ""


def test_command_line_writes_report_and_data(tmp_path, capsys):
    out = tmp_path / "saida"
    code = cli.main(["relatorio", "--csv", IXI_CSV, "--linha", "IXI002-Guys-0828-T1", "--idade", "35.8", "--sexo", "F",
                     "--saida", str(out), "--nome", "Exemplo"])
    assert code == 0
    assert (out / "relatorio.pdf").exists() and (out / "relatorio.png").exists()
    data = json.loads((out / "resultado.json").read_text(encoding="utf-8"))
    assert data["aviso"] == DISCLAIMER
    assert len(data["estruturas"]) == 10 and data["modelo"] == "female"
    assert DISCLAIMER in capsys.readouterr().out
    assert cli.main(["relatorio", "--csv", str(tmp_path / "nao-existe.csv"), "--saida", str(out)]) == 1
