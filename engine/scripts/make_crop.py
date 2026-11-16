"""Recorta um cubo do meio de um volume, para testar a segmentação em máquinas com pouca memória.

Uso: python make_crop.py ENTRADA.nii.gz SAIDA.nii.gz

Tira 128 x 128 x 100 voxels do centro do voluntário público IXI002 (cerca de 12 cm de lado). O
resultado não serve para medir ninguém: falta parte do encéfalo. Serve para comparar a mesma
imagem em duas máquinas (Linux e Mac com Apple Silicon) e ver se dão os mesmos números.
"""
import sys

import nibabel as nib

image = nib.load(sys.argv[1])
if image.shape[:3] != (256, 256, 150):
    raise SystemExit(f"esperava o volume do IXI002 (256 x 256 x 150); veio {image.shape}")
nib.save(image.slicer[86:214, 68:196, 24:124], sys.argv[2])
print("recorte gravado:", sys.argv[2])
