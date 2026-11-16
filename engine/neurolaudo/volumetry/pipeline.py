"""Volumetria de um exame, do volume T1 ao relatório.

Passos:

1. recorte da imagem na caixa da cabeça (`volume.head_box`);
2. `mri_synthseg --fast --cpu --vol`: segmentação e volumes (SynthSeg 2.0), como nas normas;
3. comparação com a referência por idade e sexo (Neurodesk, BRAINQUANT_NORMS.md);
4. relatório, página de conferência e mapa colorido.

As normas foram ajustadas com o recorte feito em volta do encéfalo pelo SynthStrip. Com ele o motor
reproduziu os volumes publicados com diferença de 0,00 % em 8 voluntários públicos (16/11/2026), mas o
SynthStrip não roda em Mac com Apple Silicon em tempo razoável, e foi trocado pela caixa da cabeça. O
efeito da troca é medido por scripts/validate_ixi.py.

O `mri_synthseg` vem do FreeSurfer 8.2.0 e não faz parte deste repositório.
Uso em pesquisa. Não validado para diagnóstico.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

import nibabel as nib
import numpy as np

from neurolaudo.volumetry import overlay, report, volume
from neurolaudo.volumetry.norms import assess, load_norms
from neurolaudo.volumetry.tables import QC_TITLES_PT, read_volumes_csv, result_json

QC_THRESHOLD = 0.65          # abaixo disso os autores do SynthSeg tratam a segmentação como suspeita
MAX_VOXEL_MM = 1.5           # acima disso a série não é um T1 volumétrico fino
PAGE_DPI = 150
SEGMENT_TIMEOUT_S = 40 * 60
MAX_ATTEMPTS = 3             # segmentações por exame: a primeira e até duas com recorte maior
MODEL_FILES = ("synthseg_2.0.h5", "synthseg_qc_2.0.h5")

Progress = Callable[[float, str], None]


class PipelineError(RuntimeError):
    """Falha da volumetria com mensagem para o usuário."""


@dataclass(frozen=True)
class Tools:
    """Como chamar o programa de segmentação."""

    synthseg: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    home: str = ""


def engine_home() -> Path:
    """Pasta onde o instalador põe o motor de segmentação."""
    custom = os.environ.get("NEUROLAUDO_MOTOR")
    if custom:
        return Path(custom)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "NeuroLaudo" / "motor"
    return Path.home() / ".local" / "share" / "neurolaudo" / "motor"


def find_tools() -> Tools:
    """Localiza o programa de segmentação. A variável NEUROLAUDO_SYNTHSEG troca o comando (testes)."""
    seg_cmd = os.environ.get("NEUROLAUDO_SYNTHSEG")
    if seg_cmd:
        return Tools(tuple(shlex.split(seg_cmd)))
    fs_home = Path(os.environ.get("NEUROLAUDO_FS_HOME") or engine_home() / "freesurfer")
    script = fs_home / "bin" / "mri_synthseg"
    missing = [str(script)] if not script.is_file() else []
    missing += [str(fs_home / "models" / m) for m in MODEL_FILES if not (fs_home / "models" / m).is_file()]
    if missing:
        raise PipelineError("O motor de segmentação não está instalado (rode o instalador da volumetria). Falta: "
                            + "; ".join(missing))
    # Sem oneDNN o TensorFlow dá os mesmos volumes com menos memória (cerca de 6 GB contra 10 GB no exame
    # de teste). No Mac com Apple Silicon o oneDNN nem existe; assim o Linux de teste anda pelo mesmo caminho.
    env = {"FREESURFER_HOME": str(fs_home), "TF_CPP_MIN_LOG_LEVEL": "3", "TF_ENABLE_ONEDNN_OPTS": "0"}
    return Tools((sys.executable, str(script)), env, str(fs_home))


def _run(command, env: Mapping[str, str], log_path: Path, what: str, timeout: int) -> None:
    full_env = dict(os.environ)
    full_env.update(env)
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            done = subprocess.run(list(command), env=full_env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    except FileNotFoundError as error:
        raise PipelineError(f"{what}: programa não encontrado ({command[0]}).") from error
    except subprocess.TimeoutExpired as error:
        raise PipelineError(f"{what}: passou do limite de {timeout // 60} minutos.") from error
    if done.returncode != 0:
        tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:])
        raise PipelineError(f"{what} falhou (código {done.returncode}). Fim do registro:\n{tail}")


def quality_summary(scores: Mapping[str, float]) -> list[str]:
    """Frase de rodapé com a menor nota automática de qualidade do SynthSeg (0 a 1)."""
    if not scores:
        return []
    worst = min(scores, key=scores.get)  # type: ignore[arg-type]
    return [f"Nota automática de qualidade da segmentação (0 a 1): a menor foi {report.br(scores[worst], 2)}, em "
            f"{QC_TITLES_PT.get(worst, worst)}."]


def quality_warnings(scores: Mapping[str, float]) -> list[str]:
    """Aviso quando alguma nota de qualidade fica abaixo do limite."""
    low = [QC_TITLES_PT.get(k, k) for k, v in scores.items() if v < QC_THRESHOLD]
    if not low:
        return []
    return [f"Nota automática de qualidade abaixo de {report.br(QC_THRESHOLD, 2)} em {', '.join(low)}. "
            "Confira a página de conferência antes de usar os números."]


def resolution_notes(zooms) -> list[str]:
    worst = max(zooms)
    if worst > MAX_VOXEL_MM:
        return [f"Série com voxel de {report.br(worst, 1)} mm na maior dimensão: a referência usa T1 volumétrico de "
                "cerca de 1 mm, e o resultado é menos confiável."]
    return []


def _write_raw(path: Path, array: np.ndarray) -> None:
    with open(path, "wb") as fh:
        fh.write(np.ascontiguousarray(array, dtype=np.uint8).tobytes())


def run_exam(nifti_path: str, out_dir: str, age: float | None, sex: str | None,
             header: report.ReportHeader | None = None, threads: int | None = None, tools: Tools | None = None,
             progress: Progress | None = None, series_notes=(), quality: bool = False, refine: bool = False) -> dict:
    """Roda a volumetria de um volume T1 e grava os resultados em `out_dir`. Devolve o conteúdo de resultado.json.

    `series_notes`: avisos sobre a série vindos de quem chamou (por exemplo, "série com contraste").
    `refine`: depois da primeira segmentação, recorta de novo pela caixa das normas (o que foi segmentado mais
    15 mm) e segmenta outra vez. Dobra o tempo; scripts/validate_ixi.py mede se compensa.
    `quality`: pede também as notas automáticas de qualidade do SynthSeg. Fica desligado por padrão por dois
    motivos medidos no exame público IXI002: com as notas, os volumes deixam de ser idênticos aos da tabela que
    ajustou as normas (até 1,3 % de diferença no córtex), e a memória necessária estoura (a rede das notas
    trabalha em 224³ voxels com filtros de 5×5×5).
    """
    say = progress or (lambda fraction, message: None)
    started = time.monotonic()
    header = header or report.ReportHeader()
    tools = tools or find_tools()
    threads = threads or max(1, min(os.cpu_count() or 1, 8))
    out = Path(out_dir)
    work = out / "trabalho"
    work.mkdir(parents=True, exist_ok=True)

    say(0.02, "Lendo o volume")
    try:
        image = volume.load_image(nifti_path)
    except volume.VolumeError as error:
        raise PipelineError(str(error)) from error
    zooms = volume.voxel_sizes(image)
    source = work / "t1.nii.gz"
    nib.save(image, str(source))

    say(0.05, "Localizando a cabeça")
    try:
        box = volume.head_box(image)
    except volume.VolumeError as error:
        raise PipelineError(str(error)) from error
    trimmed_path = work / "t1_recortado.nii.gz"
    seg_path, vol_path, qc_path = work / "segmentacao.nii.gz", work / "volumes.csv", work / "qualidade.csv"
    segment_started = time.monotonic()
    attempts = 0
    first_box = None

    def segment(current: volume.Box, fraction: float, message: str):
        """Recorta a imagem na caixa, roda o SynthSeg e devolve (imagem recortada, rótulos na grade do recorte)."""
        nonlocal attempts
        attempts += 1
        say(fraction, message)
        piece = volume.trim(image, current)
        nib.save(piece, str(trimmed_path))
        for stale in (seg_path, vol_path, qc_path):
            stale.unlink(missing_ok=True)   # o SynthSeg acrescenta linhas a tabelas que já existem
        command = [*tools.synthseg, "--i", str(trimmed_path), "--o", str(seg_path), "--vol", str(vol_path),
                   "--fast", "--cpu", "--keepgeom", "--noaddctab", "--threads", str(threads)]
        if quality:
            command += ["--qc", str(qc_path)]
        _run(command, tools.env, work / "registro-synthseg.txt", "A segmentação (SynthSeg)", SEGMENT_TIMEOUT_S)
        for needed, what in ((seg_path, "a segmentação"), (vol_path, "a tabela de volumes")):
            if not needed.is_file():
                raise PipelineError(f"A segmentação terminou sem gravar {what}.")
        found = np.asarray(nib.load(str(seg_path)).dataobj)
        if tuple(found.shape[:3]) != current.shape:
            raise PipelineError(f"A segmentação ({found.shape}) não tem a grade da imagem recortada ({current.shape}).")
        return piece, found

    try:
        trimmed, trimmed_labels = segment(box, 0.10, "Segmentando (alguns minutos)")
        # O encéfalo encostou em alguma face do recorte? Então pode ter ficado um pedaço de fora:
        # alarga a caixa desse lado e segmenta de novo (no máximo duas vezes).
        while True:
            touching = volume.touching_faces(trimmed_labels, trimmed)
            growable = [face for face in touching if not volume.at_image_edge(box, face, image.shape)]
            if not growable or attempts >= MAX_ATTEMPTS:
                break
            box = volume.grow(box, growable, zooms, image.shape)
            trimmed, trimmed_labels = segment(box, 0.40, "Segmentando de novo, com recorte maior")
        if refine:
            # Segundo passo: a caixa das normas (o que foi segmentado mais 15 mm), agora que se sabe onde
            # está o encéfalo. Os volumes do primeiro passo ficam guardados para comparação.
            refined = volume.brain_box(trimmed_labels, box, zooms, image.shape)
            if refined != box:
                shutil.copy(vol_path, work / "volumes-primeiro-passo.csv")
                first_box, box = box, refined
                trimmed, trimmed_labels = segment(box, 0.50, "Segmentando com o recorte das normas")
                touching = volume.touching_faces(trimmed_labels, trimmed)
        labels = volume.paste_labels(image.shape, box, trimmed_labels)
    except volume.VolumeError as error:
        raise PipelineError(str(error)) from error
    segment_seconds = time.monotonic() - segment_started
    edge_notes = []
    if touching:
        sides = ", ".join(sorted({volume.face_name(trimmed, face) for face in touching}))
        where = "da imagem" if all(volume.at_image_edge(box, face, image.shape) for face in touching) else "do recorte"
        edge_notes.append(f"O encéfalo segmentado encosta na borda {where} ({sides}): parte dele pode ter ficado de fora, "
                          "e os volumes podem estar subestimados.")

    say(0.85, "Comparando com a referência")
    try:
        volumes = read_volumes_csv(str(vol_path))
        assessment = assess(load_norms(), volumes, age=age, sex=sex)
        scores = read_volumes_csv(str(qc_path)) if qc_path.is_file() else {}
    except ValueError as error:
        raise PipelineError(str(error)) from error
    notes = list(series_notes) + edge_notes + quality_warnings(scores) + resolution_notes(zooms)
    footnotes = quality_summary(scores)

    say(0.90, "Montando o relatório")
    pages = [report.build_figure(assessment, header, notes, footnotes),
             overlay.montage_figure(image, labels, report.patient_line(assessment, header))]
    page_files = []
    try:
        report.save_figures_pdf(str(out / "relatorio.pdf"), pages)
        for number, (fig, png) in enumerate(zip(pages, ("relatorio.png", "conferencia.png")), start=1):
            fig.savefig(str(out / png), format="png", dpi=PAGE_DPI, facecolor=fig.get_facecolor())
            rgba = report.figure_rgba(fig, PAGE_DPI)
            _write_raw(out / f"pagina-{number}.rgba", rgba)
            page_files.append({"arquivo": f"pagina-{number}.rgba", "largura": int(rgba.shape[1]), "altura": int(rgba.shape[0])})
    finally:
        for fig in pages:
            report.plt.close(fig)

    say(0.95, "Gravando o mapa colorido")
    color_map = overlay.render_map(np.asarray(image.dataobj), labels)
    _write_raw(out / "mapa.rgba", color_map)

    result = result_json(assessment)
    result.update({
        "avisos": list(assessment.warnings) + notes,
        "qualidade": {QC_TITLES_PT.get(k, k): round(v, 3) for k, v in scores.items()},
        "entrada": {"voxels": [int(v) for v in image.shape[:3]], "voxel_mm": [round(z, 3) for z in zooms],
                    "orientacao": volume.orientation(image)},
        "recorte": {"inicio": list(box.low), "fim": list(box.high), "segmentacoes": attempts,
                    "primeiro_passo": None if first_box is None else {"inicio": list(first_box.low), "fim": list(first_box.high)}},
        "paginas": page_files,
        "mapa": {"arquivo": "mapa.rgba", "cortes": int(color_map.shape[0]), "linhas": int(color_map.shape[1]),
                 "colunas": int(color_map.shape[2])},
        "arquivos": {"pdf": "relatorio.pdf", "relatorio": "relatorio.png", "conferencia": "conferencia.png"},
        "tempos_s": {"segmentacao": round(segment_seconds, 1), "total": round(time.monotonic() - started, 1)},
        "nucleos": threads,
    })
    with open(out / "resultado.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    say(1.0, "Pronto")
    return result
