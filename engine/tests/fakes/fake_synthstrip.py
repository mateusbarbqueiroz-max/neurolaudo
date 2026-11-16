"""Faz de conta que é o mri_synthstrip: a "máscara do encéfalo" é tudo que passa de um limiar.

Só para testes do encanamento, com o fantoma. Não segmenta nada de verdade.
"""
import argparse

import nibabel as nib
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("-i")
parser.add_argument("-m")
parser.add_argument("-t")
args = parser.parse_args()
image = nib.load(args.i)
nib.save(nib.Nifti1Image((np.asarray(image.dataobj) > 50).astype(np.uint8), image.affine), args.m)
