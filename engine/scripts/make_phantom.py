"""Gera uma TC de crânio sintética (fantoma) em DICOM, para testes sem dados de pacientes.

Uso: python scripts/make_phantom.py pasta_saida
Contém: calota óssea, parênquima, ventrículos e um hematoma hiperdenso à direita.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, MRImageStorage, generate_uid


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


# Nomes de série no estilo de um exame de rotina de RM de encéfalo.
MR_SERIES = ["AX FLAIR", "AX DWI b1000", "AX ADC", "AX SWI", "SAG T1 MPRAGE", "SAG T1 MPRAGE GD"]


def write_mr_study(out: str, study_date: str, series=MR_SERIES, nz=16, ny=128, nx=128, sz=10.0, sxy=1.6,
                   patient_id="000002", accession="RM1") -> dict[str, list[str]]:
    """Grava um estudo de RM sintético, uma pasta por série. Devolve os arquivos por série.

    As imagens são o mesmo fantoma com brilho diferente em cada série: servem
    para testar protocolos de exibição e comparação, não a aparência de cada sequência.
    """
    base = np.clip(phantom(nz, ny, nx, sz, sxy) + 1024, 0, 4095)   # intensidades positivas, como em RM
    study, frame = generate_uid(), generate_uid()
    written: dict[str, list[str]] = {}
    for number, description in enumerate(series, start=1):
        series_uid = generate_uid()
        folder = os.path.join(out, f"{number:02d}")
        os.makedirs(folder, exist_ok=True)
        scale = 0.4 + 0.1 * number
        paths = []
        for k in range(nz):
            meta = FileMetaDataset()
            meta.MediaStorageSOPClassUID = MRImageStorage
            meta.MediaStorageSOPInstanceUID = generate_uid()
            meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds = Dataset()
            ds.file_meta = meta
            ds.SOPClassUID = MRImageStorage
            ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
            ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study, series_uid, frame
            ds.PatientName = "FANTOMA^RM"
            ds.PatientID = patient_id
            ds.PatientBirthDate = "19650101"
            ds.PatientSex = "O"
            ds.StudyDate = study_date
            ds.StudyTime = "120000"
            ds.StudyDescription = "RM ENCEFALO"
            ds.SeriesDescription = description
            ds.SeriesNumber = number
            ds.AccessionNumber = accession
            ds.Modality = "MR"
            ds.InstanceNumber = k + 1
            ds.ImagePositionPatient = [-(nx / 2) * sxy, -(ny / 2) * sxy, float(k) * sz]
            ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
            ds.PixelSpacing = [sxy, sxy]
            ds.SliceThickness = sz
            ds.Rows, ds.Columns = ny, nx
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 12, 11
            ds.PixelRepresentation = 0
            ds.PixelData = (base[k] * scale).astype(np.uint16).tobytes()
            p = os.path.join(folder, f"IM{k:04d}.dcm")
            ds.save_as(p, enforce_file_format=True)
            paths.append(p)
        written[description] = paths
    return written


def write_mr_pair(out: str) -> None:
    """Dois exames de RM do mesmo paciente: `anterior` (janeiro) e `atual` (novembro)."""
    write_mr_study(os.path.join(out, "anterior"), "20260110", accession="RM0")
    write_mr_study(os.path.join(out, "atual"), "20261115", accession="RM1")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--rm":
        out = args[1] if len(args) > 1 else "phantom-rm"
        write_mr_pair(out)
        print(f"Fantomas de RM gravados em {out}/anterior e {out}/atual")
    else:
        out = args[0] if args else "phantom"
        write(out)
        print(f"Fantoma gravado em {out}/")
