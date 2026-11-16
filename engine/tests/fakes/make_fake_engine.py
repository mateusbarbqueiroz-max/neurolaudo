"""Monta uma pasta de "motor" com os programas de mentira, para testar o complemento dentro do IsiX.

Uso: python make_fake_engine.py PASTA_DO_MOTOR

A pasta fica com a mesma forma da que o instalador cria (freesurfer/bin, freesurfer/models), mas
com os programas de mentira e modelos vazios. O Python (venv) é criado por quem chama.
"""
import csv
import shutil
import sys
from pathlib import Path

here = Path(__file__).parent
home = Path(sys.argv[1]) / "freesurfer"
(home / "bin").mkdir(parents=True, exist_ok=True)
(home / "models").mkdir(parents=True, exist_ok=True)
shutil.copy(here / "fake_synthstrip.py", home / "bin" / "mri_synthstrip")
shutil.copy(here / "fake_synthseg.py", home / "bin" / "mri_synthseg")
for model in ("synthseg_2.0.h5", "synthseg_qc_2.0.h5", "synthstrip.1.pt"):
    (home / "models" / model).write_bytes(b"")

# Volumes de um voluntário público, só para o relatório ter números plausíveis.
with open(here.parent / "data" / "brainquant_ixi_volumes.csv", newline="", encoding="utf-8") as fh:
    row = next(r for r in csv.DictReader(fh) if r["subject"] == "IXI072-HH-2324-T1")
columns = [c for c in row if c not in ("site", "sex", "age", "exclude")]
with open(home / "bin" / "fake_volumes.csv", "w", newline="", encoding="utf-8") as fh:
    writer = csv.writer(fh)
    writer.writerow(columns)
    writer.writerow([row[c] for c in columns])
print(f"Motor de mentira montado em {home.parent}")
