"""Mede tempo, memória e números do SynthSeg em várias configurações, no mesmo exame público.

Uso: python diagnose_segmenter.py T1.nii.gz referencia.csv SUJEITO PASTA_DE_SAIDA

Serve para escolher como o motor chama o SynthSeg: quantos núcleos, com ou sem
as notas de qualidade, com ou sem as otimizações oneDNN do TensorFlow. Para
cada configuração mostra o tempo, o pico de memória e a diferença, em %, das
estruturas do relatório em relação aos volumes publicados para o mesmo exame.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib

from neurolaudo.volumetry import volume
from neurolaudo.volumetry.norms import load_norms
from neurolaudo.volumetry.pipeline import find_tools
from neurolaudo.volumetry.tables import read_volumes_csv

# nome, opções extras do mri_synthseg, variáveis de ambiente extras
NO_DNN = {"TF_ENABLE_ONEDNN_OPTS": "0"}   # o TensorFlow do Mac com Apple Silicon não tem oneDNN
DNN = {"TF_ENABLE_ONEDNN_OPTS": "1"}
# nome, opções extras do mri_synthseg, variáveis de ambiente extras
CONFIGS = [
    ("I  sem oneDNN, 4 núcleos (motor)", ["--threads", "4", "--keepgeom"], NO_DNN),
    ("J  sem oneDNN, 1 núcleo", ["--keepgeom"], NO_DNN),
    ("K  com oneDNN, 4 núcleos", ["--threads", "4", "--keepgeom"], DNN),
]
# Caixa que o SynthStrip deu para o IXI002 (máscara mais 15 mm), medida em 16/11/2026: serve de comparação.
REFERENCE_BOX = ((47, 38, 2), (253, 227, 147))


def padded(shape, zooms) -> str:
    """Tamanho que o SynthSeg processa: reamostrado para 1 mm e completado até múltiplos de 32."""
    sizes = [int(-(-round(n * z) // 32) * 32) for n, z in zip(shape, zooms)]
    return f"{sizes[0]} x {sizes[1]} x {sizes[2]} = {sizes[0] * sizes[1] * sizes[2] / 1e6:.1f} milhões de voxels"


def main(argv: list[str]) -> int:
    t1, reference_csv, subject, out = argv[1], argv[2], argv[3], Path(argv[4])
    out.mkdir(parents=True, exist_ok=True)
    tools = find_tools()
    env = dict(os.environ)
    env.update(tools.env)
    norms = load_norms()
    published = read_volumes_csv(reference_csv, subject)

    image = volume.load_image(t1)
    zooms = volume.voxel_sizes(image)
    trimmed_path = out / "t1_recortado.nii.gz"
    box = volume.head_box(image)
    nib.save(volume.trim(image, box), str(trimmed_path))
    overcommit = Path("/proc/sys/vm/overcommit_memory")
    print(f"Imagem {image.shape}, voxel {zooms}, orientação {volume.orientation(image)}", flush=True)
    print(f"Caixa da cabeça: {box.low} a {box.high} = {box.shape} voxels; o SynthSeg processa {padded(box.shape, zooms)}")
    if image.shape[:3] == (256, 256, 150):
        reference = volume.Box(*REFERENCE_BOX)
        print(f"Caixa do SynthStrip (normas): {reference.low} a {reference.high} = {reference.shape} voxels; "
              f"o SynthSeg processa {padded(reference.shape, zooms)}")
    if overcommit.exists():
        print(f"Política de memória do Linux (overcommit_memory): {overcommit.read_text().strip()}", flush=True)

    names = [s.title for s in norms.structures] + ["VIC"]
    print(f"\n{'configuração':36s} {'tempo':>7s} {'memória':>9s}  diferença em % das estruturas do relatório (ordem: "
          + ", ".join(names) + ")", flush=True)
    for label, extra, extra_env in CONFIGS:
        folder = out / label.split()[0]
        folder.mkdir(exist_ok=True)
        options = [str(folder / "qc.csv") if o == "QC" else o for o in extra]
        command = ["/usr/bin/time", "-v", *tools.synthseg, "--i", str(trimmed_path), "--o", str(folder / "seg.nii.gz"),
                   "--vol", str(folder / "vol.csv"), "--fast", "--cpu", "--noaddctab", *options]
        run_env = dict(env)
        run_env.update(extra_env)
        started = time.monotonic()
        done = subprocess.run(command, env=run_env, capture_output=True, text=True)
        seconds = time.monotonic() - started
        peak = re.search(r"Maximum resident set size \(kbytes\): (\d+)", done.stderr)
        memory = f"{int(peak.group(1)) / 1e6:6.1f} GB" if peak else "       ?"
        if done.returncode != 0 or not (folder / "vol.csv").is_file():
            reason = "bad_alloc (faltou memória)" if "bad_alloc" in done.stderr else f"código {done.returncode}"
            if "bad_alloc" not in done.stderr:
                print("   " + " | ".join((done.stdout + done.stderr).strip().splitlines()[-4:])[:600], flush=True)
            print(f"{label:36s} {seconds:6.0f}s {memory}  FALHOU: {reason}", flush=True)
            continue
        measured = read_volumes_csv(str(folder / "vol.csv"))
        diffs = []
        for structure in norms.structures:
            here = sum(measured[c] for c in structure.columns)
            there = sum(published[c] for c in structure.columns)
            diffs.append(100.0 * (here / there - 1.0))
        diffs.append(100.0 * (measured[norms.icv_column] / published[norms.icv_column] - 1.0))
        print(f"{label:36s} {seconds:6.0f}s {memory}  " + " ".join(f"{d:+6.2f}" for d in diffs), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
