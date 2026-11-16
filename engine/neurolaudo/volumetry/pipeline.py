"""Volumetria de um exame, do volume T1 ao relatório.

Passos, iguais aos usados para ajustar as normas (Neurodesk, BRAINQUANT_NORMS.md):

1. `mri_synthstrip`: máscara do encéfalo;
2. recorte na caixa da máscara mais 15 mm;
3. `mri_synthseg --fast --cpu --vol`: segmentação e volumes (SynthSeg 2.0);
4. comparação com a referência por idade e sexo;
5. relatório, página de conferência e mapa colorido.

Os dois programas vêm do FreeSurfer 8.2.0 e não fazem parte deste repositório.
Uso em pesquisa. Não validado para diagnóstico.
"""
from __future__ import annotations

import json
import os
import shlex
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
STRIP_TIMEOUT_S = 20 * 60
SEGMENT_TIMEOUT_S = 40 * 60
MODEL_FILES = ("synthseg_2.0.h5", "synthseg_qc_2.0.h5", "synthstrip.1.pt")

Progress = Callable[[float, str], None]


class PipelineError(RuntimeError):
    """Falha da volumetria com mensagem para o usuário."""


@dataclass(frozen=True)
class Tools:
    """Como chamar os dois programas de segmentação."""

    synthstrip: tuple[str, ...]
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
    """Localiza os programas. Variáveis NEUROLAUDO_SYNTHSTRIP e NEUROLAUDO_SYNTHSEG trocam os comandos."""
    strip_cmd, seg_cmd = os.environ.get("NEUROLAUDO_SYNTHSTRIP"), os.environ.get("NEUROLAUDO_SYNTHSEG")
    if strip_cmd and seg_cmd:
        return Tools(tuple(shlex.split(strip_cmd)), tuple(shlex.split(seg_cmd)))
    fs_home = Path(os.environ.get("NEUROLAUDO_FS_HOME") or engine_home() / "freesurfer")
    scripts = {name: fs_home / "bin" / name for name in ("mri_synthstrip", "mri_synthseg")}
    missing = [str(p) for p in scripts.values() if not p.is_file()]
    missing += [str(fs_home / "models" / m) for m in MODEL_FILES if not (fs_home / "models" / m).is_file()]
    if missing:
        raise PipelineError("O motor de segmentação não está instalado (rode o instalador da volumetria). Falta: "
                            + "; ".join(missing))
    # Sem oneDNN o TensorFlow dá os mesmos volumes com menos memória (cerca de 6 GB contra 10 GB no exame
    # de teste). No Mac com Apple Silicon o oneDNN nem existe; assim o Linux de teste anda pelo mesmo caminho.
    env = {"FREESURFER_HOME": str(fs_home), "TF_CPP_MIN_LOG_LEVEL": "3", "TF_ENABLE_ONEDNN_OPTS": "0"}
    return Tools((sys.executable, str(scripts["mri_synthstrip"])), (sys.executable, str(scripts["mri_synthseg"])), env,
                 str(fs_home))


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
             progress: Progress | None = None, series_notes=(), quality: bool = False) -> dict:
    """Roda a volumetria de um volume T1 e grava os resultados em `out_dir`. Devolve o conteúdo de resultado.json.

    `series_notes`: avisos sobre a série vindos de quem chamou (por exemplo, "série com contraste").
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

    say(0.05, "Localizando o encéfalo")
    mask_path = work / "mascara.nii.gz"
    _run([*tools.synthstrip, "-i", str(source), "-m", str(mask_path), "-t", str(threads)], tools.env,
         work / "registro-synthstrip.txt", "A localização do encéfalo (SynthStrip)", STRIP_TIMEOUT_S)
    if not mask_path.is_file():
        raise PipelineError("A localização do encéfalo terminou sem gravar a máscara.")
    try:
        trimmed, box = volume.trim_to_mask(image, nib.load(str(mask_path)))
    except volume.VolumeError as error:
        raise PipelineError(str(error)) from error
    trimmed_path = work / "t1_recortado.nii.gz"
    nib.save(trimmed, str(trimmed_path))

    say(0.20, "Segmentando (alguns minutos)")
    seg_path, vol_path, qc_path = work / "segmentacao.nii.gz", work / "volumes.csv", work / "qualidade.csv"
    for stale in (seg_path, vol_path, qc_path):
        stale.unlink(missing_ok=True)   # o SynthSeg acrescenta linhas a tabelas que já existem
    segment_started = time.monotonic()
    command = [*tools.synthseg, "--i", str(trimmed_path), "--o", str(seg_path), "--vol", str(vol_path),
               "--fast", "--cpu", "--keepgeom", "--noaddctab", "--threads", str(threads)]
    if quality:
        command += ["--qc", str(qc_path)]
    _run(command, tools.env, work / "registro-synthseg.txt", "A segmentação (SynthSeg)", SEGMENT_TIMEOUT_S)
    segment_seconds = time.monotonic() - segment_started
    for needed, what in ((seg_path, "a segmentação"), (vol_path, "a tabela de volumes")):
        if not needed.is_file():
            raise PipelineError(f"A segmentação terminou sem gravar {what}.")

    say(0.85, "Comparando com a referência")
    try:
        volumes = read_volumes_csv(str(vol_path))
        assessment = assess(load_norms(), volumes, age=age, sex=sex)
        scores = read_volumes_csv(str(qc_path)) if qc_path.is_file() else {}
        labels = volume.paste_labels(image.shape, box, np.asarray(nib.load(str(seg_path)).dataobj))
    except (ValueError, volume.VolumeError) as error:
        raise PipelineError(str(error)) from error
    notes = list(series_notes) + quality_warnings(scores) + resolution_notes(zooms)
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
        "recorte": {"inicio": list(box.low), "fim": list(box.high)},
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
