"""Diálogos das calculadoras e configurações."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGridLayout, QLabel, QLineEdit, QVBoxLayout)

from neurolaudo.reports.calculators import ASPECTS_REGIONS, abc2_volume, aspects_score


class AspectsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ASPECTS")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Marque as regiões com sinais de isquemia precoce:"))
        grid = QGridLayout()
        self.boxes: dict[str, QCheckBox] = {}
        for i, (code, name) in enumerate(ASPECTS_REGIONS):
            cb = QCheckBox(f"{code} — {name}")
            cb.toggled.connect(self._update)
            self.boxes[code] = cb
            grid.addWidget(cb, i % 5, i // 5)
        lay.addLayout(grid)
        self.result = QLabel()
        self.result.setStyleSheet("font-size:16pt; font-weight:bold")
        lay.addWidget(self.result)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._update()

    def affected(self) -> set[str]:
        return {c for c, cb in self.boxes.items() if cb.isChecked()}

    def score(self) -> int:
        return aspects_score(self.affected())

    def _update(self):
        self.result.setText(f"ASPECTS = {self.score()}")

    def text(self) -> str:
        aff = sorted(self.affected(), key=[c for c, _ in ASPECTS_REGIONS].index)
        if not aff:
            return "10 (sem regiões acometidas)"
        return f"{self.score()} (acometimento de: {', '.join(aff)})"


class Abc2Dialog(QDialog):
    def __init__(self, parent=None, last_measure_mm: float | None = None):
        super().__init__(parent)
        self.setWindowTitle("Volume de hematoma (ABC/2)")
        form = QFormLayout(self)
        self.a, self.b, self.c = (QDoubleSpinBox() for _ in range(3))
        for sb in (self.a, self.b, self.c):
            sb.setRange(0, 30)
            sb.setDecimals(1)
            sb.setSuffix(" cm")
            sb.valueChanged.connect(self._update)
        if last_measure_mm:
            self.a.setValue(last_measure_mm / 10)
        form.addRow("A — maior diâmetro axial", self.a)
        form.addRow("B — perpendicular a A", self.b)
        form.addRow("C — extensão craniocaudal", self.c)
        self.result = QLabel()
        self.result.setStyleSheet("font-size:16pt; font-weight:bold")
        form.addRow(self.result)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self._update()

    def volume(self) -> float:
        return abc2_volume(self.a.value(), self.b.value(), self.c.value())

    def _update(self):
        self.result.setText(f"Volume ≈ {self.volume():.1f} mL")

    def text(self) -> str:
        return (f"Hematoma medindo {self.a.value():.1f} x {self.b.value():.1f} x {self.c.value():.1f} cm, "
                f"com volume estimado de {self.volume():.1f} mL (método ABC/2).")


class SettingsDialog(QDialog):
    FIELDS = [("institution", "Instituição"), ("physician", "Médico(a)"), ("crm", "CRM")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações do laudo")
        self.settings = QSettings("NeuroLaudo", "NeuroLaudo")
        form = QFormLayout(self)
        self.edits: dict[str, QLineEdit] = {}
        for key, label in self.FIELDS:
            e = QLineEdit(self.settings.value(key, ""))
            self.edits[key] = e
            form.addRow(label, e)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _save(self):
        for key, e in self.edits.items():
            self.settings.setValue(key, e.text())
        self.accept()
