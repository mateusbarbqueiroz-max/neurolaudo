"""Confere que o volume gravado pelo complemento (Swift) é lido corretamente pelo motor (Python).

Uso: python check_swift_nifti.py arquivo.nii

O arquivo vem do teste VolumeGridTests.testWriteSampleVolumeForTheEngine: série sagital de
8 colunas x 10 linhas x 6 cortes, voxel de 0,9 x 1,1 x 1,2 mm, colunas para posterior, linhas
para inferior, cortes para a direita; o valor de cada voxel é coluna + 10*linha + 100*corte.
"""
import sys

import nibabel as nib
import numpy as np

image = nib.load(sys.argv[1])
data = np.asarray(image.dataobj)
assert image.shape == (8, 10, 6), image.shape
assert np.allclose(image.header.get_zooms(), (0.9, 1.1, 1.2), atol=1e-5), image.header.get_zooms()
assert "".join(nib.aff2axcodes(image.affine)) == "PIR", nib.aff2axcodes(image.affine)
i, j, k = np.meshgrid(np.arange(8), np.arange(10), np.arange(6), indexing="ij")
assert np.array_equal(data, i + 10 * j + 100 * k), "valores fora de ordem"
# Primeiro voxel: 30 mm à esquerda, 40 mm à frente, 50 mm acima (RAS: -30, +40, +50).
assert np.allclose(image.affine[:3, 3], (-30, 40, 50), atol=1e-4), image.affine[:3, 3]
# Andar um corte leva 1,2 mm para a direita do paciente.
assert np.allclose(image.affine[:3, 2], (1.2, 0, 0), atol=1e-5), image.affine[:3, 2]
print("O volume gravado pelo complemento foi lido pelo motor: forma, voxel, orientação e valores conferem.")
