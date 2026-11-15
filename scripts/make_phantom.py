"""Gera uma TC de crânio sintética (fantoma) em DICOM, para testes sem dados de pacientes.

Uso: python scripts/make_phantom.py pasta_saida
Contém: calota óssea, parênquima, ventrículos e um hematoma hiperdenso à direita.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid


def phantom(nz=64, ny=256, nx=256, sz=2.5, sxy=0.8) -> np.ndarray:
    z, y, x = np.mgrid[0:nz, 0:ny, 0:nx].astype(np.float32)
    zc, yc, xc = nz / 2, ny / 2, nx / 2
    # coordenadas físicas em mm
    Z, Y, X = (z - zc) * sz, (y - yc) * sxy, (x - xc) * sxy
    r_out = (X / 75) ** 2 + (Y / 92) ** 2 + (Z / 75) ** 2
    r_in = (X / 69) ** 2 + (Y / 86) ** 2 + (Z / 69) ** 2
    hu = np.full(X.shape, -1000, np.float32)
    hu[r_out <= 1] = 1000                      # osso
    hu[r_in <= 1] = 32                         # substância branca
    cortex = (r_in <= 1) & (r_in > 0.8)
    hu[cortex] = 40                            # substância cinzenta
    for side in (-1, 1):                       # ventrículos laterais
        v = ((X - side * 9) / 6) ** 2 + ((Y + 5) / 28) ** 2 + ((Z - 10) / 14) ** 2
        hu[v <= 1] = 5
    hem = ((X + 35) / 14) ** 2 + ((Y - 10) / 10) ** 2 + ((Z - 5) / 12) ** 2
    hu[hem <= 1] = 65                          # hematoma no hemisfério direito (esq. da imagem)
    rng = np.random.default_rng(0)
    hu += rng.normal(0, 3, hu.shape).astype(np.float32)
    return hu


def write(out: str, nz=64, ny=256, nx=256, sz=2.5, sxy=0.8) -> list[str]:
    os.makedirs(out, exist_ok=True)
    vol = phantom(nz, ny, nx, sz, sxy)
    study, series, frame = generate_uid(), generate_uid(), generate_uid()
    paths = []
    order = np.random.default_rng(1).permutation(nz)  # grava fora de ordem de propósito
    for k in order:
        meta = FileMetaDataset()
        meta.MediaStorageSOPClassUID = CTImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds = Dataset()
        ds.file_meta = meta
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study, series, frame
        ds.PatientName = "FANTOMA^TESTE"
        ds.PatientID = "000001"
        ds.PatientBirthDate = "19700101"
        ds.PatientSex = "O"
        ds.StudyDate = "20261115"
        ds.StudyDescription = "TC CRANIO SEM CONTRASTE"
        ds.SeriesDescription = "Axial 2.5mm"
        ds.AccessionNumber = "A123"
        ds.Modality = "CT"
        ds.InstanceNumber = int(k) + 1
        ds.ImagePositionPatient = [-(nx / 2) * sxy, -(ny / 2) * sxy, float(k) * sz]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.PixelSpacing = [sxy, sxy]
        ds.SliceThickness = sz
        ds.Rows, ds.Columns = ny, nx
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
        ds.PixelRepresentation = 1
        ds.RescaleIntercept, ds.RescaleSlope = -1024, 1
        ds.WindowCenter, ds.WindowWidth = 40, 80
        ds.PixelData = (vol[k] + 1024).astype(np.int16).tobytes()
        p = os.path.join(out, f"IM{k:04d}.dcm")
        ds.save_as(p, enforce_file_format=True)
        paths.append(p)
    return paths


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "phantom"
    write(out)
    print(f"Fantoma gravado em {out}/")
