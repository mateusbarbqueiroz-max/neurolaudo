"""Faz de conta que é o mri_synthseg: rótulos por limiar e por lado, volumes copiados de uma tabela.

Só para testes do encanamento, com o fantoma. Não segmenta nada de verdade:
- "substância branca" (2) onde o valor passa de 50;
- "hipocampo esquerdo" (17) e "direito" (53) onde passa de 150, conforme o lado do paciente;
- a tabela de volumes vem de FAKE_VOLUMES ou de fake_volumes.csv ao lado deste arquivo.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

parser = argparse.ArgumentParser()
for name in ("--i", "--o", "--vol", "--qc", "--threads"):
    parser.add_argument(name)
for name in ("--fast", "--cpu", "--keepgeom", "--noaddctab"):
    parser.add_argument(name, action="store_true")
args = parser.parse_args()
if os.environ.get("FAKE_FAIL"):
    print("erro simulado do segmentador")
    sys.exit(3)
assert args.fast and args.cpu and args.keepgeom, "opções das normas ausentes"
image = nib.load(args.i)
data = np.asarray(image.dataobj)
i, j, k = np.meshgrid(*[np.arange(n) for n in data.shape], indexing="ij")
x = image.affine[0, 0] * i + image.affine[0, 1] * j + image.affine[0, 2] * k + image.affine[0, 3]
labels = np.zeros(data.shape, np.int16)
labels[data > 50] = 2
labels[(data > 150) & (x < 0)] = 17      # x negativo em RAS = esquerda do paciente
labels[(data > 150) & (x > 0)] = 53
# Para testar o recorte que cresce: na primeira chamada, "córtex" encostado na primeira face do volume.
marker = os.environ.get("FAKE_TOUCH_ONCE")
if marker and not os.path.exists(marker):
    Path(marker).write_text("feito")
    labels[0, data.shape[1] // 2, data.shape[2] // 2] = 3
nib.save(nib.Nifti1Image(labels, image.affine), args.o)
shutil.copy(os.environ.get("FAKE_VOLUMES") or Path(__file__).with_name("fake_volumes.csv"), args.vol)
if args.qc:
    low = "0.41" if os.environ.get("FAKE_LOW_QC") else "0.83"
    with open(args.qc, "w") as fh:
        fh.write("subject,general white matter,general grey matter,hippocampus+amygdala\n")
        fh.write("t1_recortado,0.91,0.88," + low + "\n")
