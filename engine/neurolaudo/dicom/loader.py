"""Leitura de pastas DICOM, agrupamento em séries e montagem de volumes 3D."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError


@dataclass
class Series:
    uid: str
    description: str
    modality: str
    patient_name: str
    patient_id: str
    patient_birth: str
    patient_sex: str
    study_date: str
    study_description: str
    accession: str
    files: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.modality} · {self.description or 'sem descrição'} ({len(self.files)} img)"


@dataclass
class Volume:
    """Volume em unidades físicas (HU para TC), eixo 0 = cortes, ordenados de inferior p/ superior."""
    data: np.ndarray          # (z, y, x) float32
    spacing: tuple[float, float, float]  # (z, y, x) em mm
    series: Series
    default_window: tuple[float, float] | None = None  # (centro, largura)


def _get(ds, name, default=""):
    v = getattr(ds, name, default)
    return str(v) if v is not None else default


def scan_folder(path: str) -> list[Series]:
    """Varre recursivamente uma pasta e agrupa os arquivos DICOM por SeriesInstanceUID."""
    series: dict[str, Series] = {}
    for root, _dirs, names in os.walk(path):
        for name in names:
            fp = os.path.join(root, name)
            try:
                ds = pydicom.dcmread(fp, stop_before_pixels=True)
            except (InvalidDicomError, OSError, ValueError):
                continue
            uid = _get(ds, "SeriesInstanceUID")
            if not uid:
                continue
            if uid not in series:
                series[uid] = Series(
                    uid=uid,
                    description=_get(ds, "SeriesDescription"),
                    modality=_get(ds, "Modality"),
                    patient_name=_get(ds, "PatientName").replace("^", " ").strip(),
                    patient_id=_get(ds, "PatientID"),
                    patient_birth=_get(ds, "PatientBirthDate"),
                    patient_sex=_get(ds, "PatientSex"),
                    study_date=_get(ds, "StudyDate"),
                    study_description=_get(ds, "StudyDescription"),
                    accession=_get(ds, "AccessionNumber"),
                )
            series[uid].files.append(fp)
    return sorted(series.values(), key=lambda s: (s.study_date, s.description))


def _slice_position(ds) -> float:
    """Posição do corte ao longo da normal do plano (robusto para aquisições oblíquas)."""
    iop = getattr(ds, "ImageOrientationPatient", None)
    ipp = getattr(ds, "ImagePositionPatient", None)
    if iop is not None and ipp is not None:
        row = np.array(iop[:3], dtype=float)
        col = np.array(iop[3:], dtype=float)
        normal = np.cross(row, col)
        return float(np.dot(normal, np.array(ipp, dtype=float)))
    return float(getattr(ds, "InstanceNumber", 0) or 0)


def load_volume(series: Series) -> Volume:
    datasets = [pydicom.dcmread(f) for f in series.files]
    datasets = [d for d in datasets if "PixelData" in d]
    if not datasets:
        raise ValueError("Série sem dados de imagem")
    # mantém apenas cortes com a mesma matriz do primeiro
    shape = (int(datasets[0].Rows), int(datasets[0].Columns))
    datasets = [d for d in datasets if (int(d.Rows), int(d.Columns)) == shape]
    datasets.sort(key=_slice_position)

    slices = []
    for d in datasets:
        arr = d.pixel_array.astype(np.float32)
        slope = float(getattr(d, "RescaleSlope", 1) or 1)
        inter = float(getattr(d, "RescaleIntercept", 0) or 0)
        slices.append(arr * slope + inter)
    data = np.stack(slices, axis=0)

    ps = getattr(datasets[0], "PixelSpacing", [1.0, 1.0])
    sy, sx = float(ps[0]), float(ps[1])
    if len(datasets) > 1:
        pos = np.array([_slice_position(d) for d in datasets])
        diffs = np.abs(np.diff(pos))
        diffs = diffs[diffs > 1e-3]
        sz = float(np.median(diffs)) if diffs.size else 1.0
    else:
        sz = float(getattr(datasets[0], "SliceThickness", 1.0) or 1.0)

    window = None
    wc = getattr(datasets[0], "WindowCenter", None)
    ww = getattr(datasets[0], "WindowWidth", None)
    if wc is not None and ww is not None:
        wc = wc[0] if isinstance(wc, pydicom.multival.MultiValue) else wc
        ww = ww[0] if isinstance(ww, pydicom.multival.MultiValue) else ww
        window = (float(wc), float(ww))

    return Volume(data=data, spacing=(sz, sy, sx), series=series, default_window=window)
