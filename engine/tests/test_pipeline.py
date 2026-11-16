"""Volumetria de ponta a ponta com um programa de mentira no lugar do SynthSeg.

Confere o encanamento (recorte, tabelas, relatório, mapa), não a segmentação.
A segmentação de verdade é testada no GitHub (.github/workflows/volumetria.yml).
"""
import csv
import json
import os
import sys

import nibabel as nib
import numpy as np
import pytest

from neurolaudo.volumetry import cli, overlay, pipeline, volume
from neurolaudo.volumetry.report import ReportHeader

IXI_CSV = os.path.join(os.path.dirname(__file__), "data", "brainquant_ixi_volumes.csv")
SUBJECT = "IXI072-HH-2324-T1"

FAKES = os.path.join(os.path.dirname(__file__), "fakes")


def make_t1(path, shape=(72, 88, 64)):
    """T1 de mentira, 1 mm, como uma série sagital: colunas para posterior, linhas para inferior, cortes para a esquerda.

    Um elipsoide fora do centro faz de encéfalo; duas bolas claras fazem de hipocampos, a esquerda maior.
    """
    affine = np.array([[0.0, 0.0, -1.0, 30.0],     # x (direita) cai com o índice do corte
                       [-1.0, 0.0, 0.0, 40.0],     # y (anterior) cai com o índice da coluna
                       [0.0, -1.0, 0.0, 50.0],     # z (superior) cai com o índice da linha
                       [0.0, 0.0, 0.0, 1.0]])
    i, j, k = np.meshgrid(*[np.arange(n) for n in shape], indexing="ij")
    world = np.stack([affine[r, 0] * i + affine[r, 1] * j + affine[r, 2] * k + affine[r, 3] for r in range(3)])
    centre = np.array([2.0, 0.0, 10.0])
    radius = np.array([14.0, 18.0, 16.0])
    inside = sum(((world[n] - centre[n]) / radius[n]) ** 2 for n in range(3)) <= 1.0
    data = np.full(shape, 5.0, dtype=np.float32)
    data[inside] = 100.0
    left = sum((world[n] - (-6.0, 0.0, 8.0)[n]) ** 2 for n in range(3)) <= 4.0 ** 2
    right = sum((world[n] - (9.0, 0.0, 8.0)[n]) ** 2 for n in range(3)) <= 2.5 ** 2
    data[left | right] = 200.0
    nib.save(nib.Nifti1Image(data, affine), str(path))
    return affine, data


@pytest.fixture()
def fake_tools(tmp_path, monkeypatch):
    seg = os.path.join(FAKES, "fake_synthseg.py")
    volumes = tmp_path / "volumes.csv"
    with open(IXI_CSV, newline="", encoding="utf-8") as fh:
        row = next(r for r in csv.DictReader(fh) if r["subject"] == SUBJECT)
    columns = [c for c in row if c not in ("site", "sex", "age", "exclude")]
    with open(volumes, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        writer.writerow([row[c] for c in columns])
    monkeypatch.setenv("FAKE_VOLUMES", str(volumes))
    monkeypatch.setenv("NEUROLAUDO_SYNTHSEG", f"{sys.executable} {seg}")
    return tmp_path


def test_exam_from_volume_to_report_and_map(fake_tools, tmp_path):
    t1, out = tmp_path / "t1.nii", tmp_path / "saida"
    affine, data = make_t1(t1)
    steps = []
    result = pipeline.run_exam(str(t1), str(out), age=68.6, sex="M", header=ReportHeader(patient_name="Fantoma"),
                               progress=lambda fraction, message: steps.append((fraction, message)))

    assert steps[0][0] < steps[-1][0] == 1.0
    assert result["qualidade"] == {}      # as notas de qualidade só vêm quando pedidas
    assert result["modelo"] == "male" and len(result["estruturas"]) == 10
    assert json.loads((out / "resultado.json").read_text(encoding="utf-8")) == result
    assert (out / "relatorio.pdf").read_bytes().startswith(b"%PDF")
    assert (out / "relatorio.png").exists() and (out / "conferencia.png").exists()

    # O recorte tira ar em volta, sem cortar nada do que é cabeça.
    low, high = result["recorte"]["inicio"], result["recorte"]["fim"]
    occupied = np.argwhere(data > 50)
    assert all(l <= int(v) for l, v in zip(low, occupied.min(0)))
    assert all(h > int(v) for h, v in zip(high, occupied.max(0)))
    assert np.prod([h - l for l, h in zip(low, high)]) < 0.8 * data.size

    # As páginas e o mapa têm o tamanho que o resultado declara.
    for page in result["paginas"]:
        assert (out / page["arquivo"]).stat().st_size == page["largura"] * page["altura"] * 4
    info = result["mapa"]
    assert (info["colunas"], info["linhas"], info["cortes"]) == data.shape
    raw = np.frombuffer((out / "mapa.rgba").read_bytes(), dtype=np.uint8)
    color_map = raw.reshape(info["cortes"], info["linhas"], info["colunas"], 4)
    assert (color_map[..., 3] == 255).all()

    # O voxel do "hipocampo esquerdo" (x negativo) sai na cor do esquerdo; o do direito, na do direito.
    inverse = np.linalg.inv(affine)
    for point, label in (((-6.0, 0.0, 8.0), 17), ((9.0, 0.0, 8.0), 53)):
        i, j, k = (int(round(v)) for v in (inverse @ np.array([*point, 1.0]))[:3])
        r, g, b, alpha = overlay.LABEL_STYLE[label]
        expected = np.round(255 * (1 - alpha) + np.array([r, g, b]) * alpha)
        assert np.abs(color_map[k, j, i, :3].astype(float) - expected).max() <= 2
    # Fora do encéfalo o mapa é cinza puro.
    assert len(set(color_map[0, 0, 0, :3].tolist())) == 1


def test_low_quality_score_becomes_a_warning(fake_tools, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_LOW_QC", "1")
    t1 = tmp_path / "t1.nii"
    make_t1(t1)
    result = pipeline.run_exam(str(t1), str(tmp_path / "saida"), age=40, sex="F", quality=True)
    assert result["qualidade"]["hipocampo e amígdala"] == 0.41
    assert any("abaixo de 0,65" in w and "hipocampo e amígdala" in w for w in result["avisos"])


def test_segmenter_failure_is_reported_with_its_log(fake_tools, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_FAIL", "1")
    t1 = tmp_path / "t1.nii"
    make_t1(t1)
    with pytest.raises(pipeline.PipelineError) as error:
        pipeline.run_exam(str(t1), str(tmp_path / "saida"), age=40, sex="F")
    assert "SynthSeg" in str(error.value) and "erro simulado do segmentador" in str(error.value)


def test_missing_engine_is_explained(tmp_path, monkeypatch):
    for name in ("NEUROLAUDO_SYNTHSEG", "NEUROLAUDO_FS_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NEUROLAUDO_MOTOR", str(tmp_path / "vazio"))
    with pytest.raises(pipeline.PipelineError) as error:
        pipeline.find_tools()
    assert "não está instalado" in str(error.value) and "synthseg_2.0.h5" in str(error.value)
    assert cli.main(["verificar"]) == 1


def test_command_line_reads_the_header_file(fake_tools, tmp_path, capsys):
    t1, out, header = tmp_path / "t1.nii", tmp_path / "saida", tmp_path / "cabecalho.json"
    make_t1(t1)
    header.write_text(json.dumps({"nome": "Fantoma", "id": "000002", "idade": 68.6, "sexo": "M", "data": "20261115",
                                  "serie": "SAG T1 MPRAGE", "avisos": ["A série parece ter contraste."]}), encoding="utf-8")
    progress = tmp_path / "andamento.txt"
    assert cli.main(["exame", "--nifti", str(t1), "--saida", str(out), "--cabecalho", str(header),
                     "--progresso", str(progress)]) == 0
    printed = capsys.readouterr().out
    assert "PROGRESSO 1.00 Pronto" in printed and "Uso em pesquisa" in printed
    assert progress.read_text(encoding="utf-8") == "1.00\tPronto\n"
    result = json.loads((out / "resultado.json").read_text(encoding="utf-8"))
    assert result["modelo"] == "male" and result["idade"] == 68.6
    assert "A série parece ter contraste." in result["avisos"]
    assert result["resumo"][0].startswith("Hipocampo esquerdo: 3,7 mL, percentil 2")
    assert result["frase_laudo"].startswith("Volumetria cerebral automática (SynthSeg 2.0; percentis para a idade e o sexo;")
    assert "hipocampo direito 3,2 mL (percentil < 1)" in result["frase_laudo"]
    assert result["frase_laudo"].endswith("Assimetria dos hipocampos de 14,4 % (esquerdo maior).")
    assert cli.main(["verificar"]) == 0


def test_volume_checks(tmp_path):
    flat = tmp_path / "plano.nii"
    nib.save(nib.Nifti1Image(np.zeros((64, 64, 4), dtype=np.float32), np.eye(4)), str(flat))
    with pytest.raises(volume.VolumeError):
        volume.load_image(str(flat))
    assert pipeline.resolution_notes((1.0, 1.0, 5.0)) and not pipeline.resolution_notes((1.0, 1.0, 1.2))


def synthetic_head(affine, shape):
    """Cabeça de mentira em coordenadas do paciente (RAS, mm): topo em z = 115, pescoço, nariz e um ponto solto acima."""
    i, j, k = np.meshgrid(*[np.arange(n, dtype=np.float32) for n in shape], indexing="ij", sparse=True)
    x, y, z = (affine[r, 0] * i + affine[r, 1] * j + affine[r, 2] * k + affine[r, 3] for r in range(3))
    data = np.random.default_rng(0).normal(4, 2, shape).astype(np.float32)              # ruído do ar
    skull = (x / 80) ** 2 + ((y - 5) / 100) ** 2 + ((z - 20) / 95) ** 2 <= 1
    neck = (x ** 2 + (y - 20) ** 2 <= 55 ** 2) & (z < -40)
    nose = (np.abs(x) < 15) & (y > 100) & (y < 128) & (z > -40) & (z < 0)
    data[skull | neck | nose] = 120
    data[(np.abs(x - 60) < 3) & (np.abs(y) < 3) & (np.abs(z - 128) < 3)] = 300          # artefato acima da cabeça
    return nib.Nifti1Image(data, affine)


@pytest.mark.parametrize("affine, shape", [
    (np.array([[1, 0, 0, -120.0], [0, 1, 0, -125.0], [0, 0, 2, -140.0], [0, 0, 0, 1]]), (240, 256, 140)),     # axial
    (np.array([[0, 0, 1.2, -110.0], [-1, 0, 0, 130.0], [0, -1, 0, 135.0], [0, 0, 0, 1]]), (256, 280, 190)),   # sagital
])
def test_head_box_runs_from_the_scalp_top_down_18_cm(affine, shape):
    image = synthetic_head(affine, shape)
    box = volume.head_box(image)
    corners = np.array([affine @ np.array([*box.low, 1.0]), affine @ np.array([v - 1 for v in box.high] + [1.0])])[:, :3]
    low, high = corners.min(0), corners.max(0)
    # Em cima: o topo da cabeça (115 mm) mais a folga; o artefato a 128 mm não conta. Embaixo: 18 cm abaixo do topo.
    assert 116 <= high[2] <= 124 and -70 <= low[2] <= -60
    # Dos lados e atrás: a cabeça mais a folga. Na frente: até o nariz (128 mm), ou até onde a imagem vai.
    assert -92 <= low[0] <= -81 and 81 <= high[0] <= 92
    assert -108 <= low[1] <= -96 and high[1] >= 127
    trimmed, same = volume.trim_to_head(image)
    assert same == box and trimmed.shape == box.shape


def test_head_box_refuses_an_image_without_a_head():
    with pytest.raises(volume.VolumeError):
        volume.head_box(nib.Nifti1Image(np.zeros((64, 64, 64), dtype=np.float32), np.eye(4)))
    noise = np.random.default_rng(1).normal(100, 1, (64, 64, 64)).astype(np.float32)
    box = volume.head_box(nib.Nifti1Image(noise, np.eye(4)))     # imagem toda "cheia": a caixa é a imagem
    assert box.low == (0, 0, 0)


def test_screen_convention_puts_patient_right_on_the_left():
    # Volume em orientação RAS: índice x cresce para a direita, y para anterior, z para superior.
    axial = np.zeros((5, 7))
    axial[4, 6] = 1            # direita e anterior
    shown = overlay._display(axial)
    assert shown.shape == (7, 5) and shown[0, 0] == 1      # em cima, à esquerda da tela
    sagittal = np.zeros((7, 9))
    sagittal[6, 8] = 1         # anterior e superior
    assert overlay._display(sagittal)[0, 0] == 1           # em cima, anterior à esquerda


def test_fake_engine_folder_and_t1_phantom_work_together(tmp_path, monkeypatch):
    """O mesmo arranjo do teste dentro do IsiX: motor de mentira em pasta + fantoma de T1 em DICOM."""
    import subprocess

    import pydicom

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import make_phantom

    for name in ("NEUROLAUDO_SYNTHSEG", "NEUROLAUDO_FS_HOME", "FAKE_VOLUMES"):
        monkeypatch.delenv(name, raising=False)
    home = tmp_path / "motor"
    subprocess.run([sys.executable, os.path.join(FAKES, "make_fake_engine.py"), str(home)], check=True, capture_output=True)
    monkeypatch.setenv("NEUROLAUDO_MOTOR", str(home))

    # O fantoma em DICOM: série sagital, esfera maior à esquerda do paciente (x positivo em LPS).
    files = make_phantom.write_t1_study(str(tmp_path / "t1"))
    first = pydicom.dcmread(files[0])
    assert len(files) == 96 and first.SeriesDescription == "SAG T1 MPRAGE"
    assert [float(v) for v in first.ImageOrientationPatient] == [0, 1, 0, 0, 0, -1]
    data, x, y0, z0 = make_phantom.t1_volume()
    assert (data[x > 0] == 200).sum() > 3 * (data[x < 0] == 200).sum()

    # O mesmo volume como o complemento o gravaria: [coluna, linha, corte], cortes da esquerda para a direita.
    order = np.argsort(-x)
    volume_data = np.transpose(data[order], (2, 1, 0)).astype(np.float32)
    affine = np.array([[0, 0, 1.25, -x[order[0]]], [-1.25, 0, 0, -y0], [0, -1.25, 0, z0], [0, 0, 0, 1]])
    t1 = tmp_path / "t1.nii"
    nib.save(nib.Nifti1Image(volume_data, affine), str(t1))
    result = pipeline.run_exam(str(t1), str(tmp_path / "saida"), age=68.7, sex="F")
    assert result["entrada"]["orientacao"] == "PIR"
    assert result["mapa"] == {"arquivo": "mapa.rgba", "cortes": 96, "linhas": 112, "colunas": 128}
