"""Janela principal: navegador de séries, visualizador MPR e painel de laudo."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QComboBox, QDockWidget, QFileDialog, QGridLayout, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QPushButton, QSpinBox, QToolBar, QVBoxLayout,
                               QWidget)

from neurolaudo.dicom.loader import Series, load_volume, scan_folder
from neurolaudo.imaging.mpr import Plane
from neurolaudo.imaging.windowing import CT_PRESETS, auto_window
from neurolaudo.reports.export import ReportHeader, export_pdf
from neurolaudo.reports.templates import TEMPLATES, render_text
from neurolaudo.ui.dialogs import Abc2Dialog, AspectsDialog, SettingsDialog
from neurolaudo.ui.viewer import SliceViewer, Tool


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeuroLaudo — Neurorradiologia")
        self.resize(1500, 900)
        self.volume = None
        self.last_measure_mm: float | None = None

        # --- visualizadores
        self.viewers = {p: SliceViewer(p) for p in Plane}
        central = QWidget()
        self.grid = QGridLayout(central)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(2)
        self.setCentralWidget(central)
        for v in self.viewers.values():
            v.windowChanged.connect(self._sync_window)
            v.voxelPicked.connect(self._sync_cross)
            v.measured.connect(self._on_measure)
        self._set_layout("mpr")

        self._build_toolbar()
        self._build_series_dock()
        self._build_report_dock()
        self.statusBar().showMessage("Arquivo ▸ Abrir pasta DICOM (Ctrl+O)")

    # ================================================================ UI
    def _build_toolbar(self):
        tb = QToolBar("Ferramentas")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_open = QAction("Abrir pasta", self, shortcut=QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._ask_folder)
        tb.addAction(act_open)
        tb.addSeparator()

        group = QActionGroup(self)
        for tool in Tool:
            a = QAction(tool.value, self, checkable=True)
            a.setChecked(tool == Tool.WINDOW)
            a.triggered.connect(lambda _=False, t=tool: self._set_tool(t))
            group.addAction(a)
            tb.addAction(a)
        tb.addSeparator()

        tb.addWidget(QLabel(" Janela: "))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Padrão da série")
        for name, c, w in CT_PRESETS:
            self.preset_combo.addItem(f"{name} ({c}/{w})", (c, w))
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        tb.addWidget(self.preset_combo)
        tb.addSeparator()

        tb.addWidget(QLabel(" Slab: "))
        self.slab_spin = QSpinBox()
        self.slab_spin.setRange(1, 99)
        self.slab_spin.setSuffix(" cortes")
        self.slab_combo = QComboBox()
        self.slab_combo.addItem("Média", "avg")
        self.slab_combo.addItem("MIP", "mip")
        self.slab_combo.addItem("MinIP", "minip")
        self.slab_spin.valueChanged.connect(self._apply_slab)
        self.slab_combo.currentIndexChanged.connect(self._apply_slab)
        tb.addWidget(self.slab_spin)
        tb.addWidget(self.slab_combo)
        tb.addSeparator()

        tb.addWidget(QLabel(" Layout: "))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("MPR (3 planos)", "mpr")
        for p in Plane:
            self.layout_combo.addItem(p.value, p.value)
        self.layout_combo.currentIndexChanged.connect(
            lambda: self._set_layout(self.layout_combo.currentData()))
        tb.addWidget(self.layout_combo)

        act_cfg = QAction("Configurações", self)
        act_cfg.triggered.connect(lambda: SettingsDialog(self).exec())
        tb.addSeparator()
        tb.addAction(act_cfg)

    def _build_series_dock(self):
        dock = QDockWidget("Séries", self)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        w = QWidget()
        lay = QVBoxLayout(w)
        self.patient_label = QLabel("Nenhum exame aberto")
        self.patient_label.setWordWrap(True)
        lay.addWidget(self.patient_label)
        self.series_list = QListWidget()
        self.series_list.itemDoubleClicked.connect(self._load_series_item)
        self.series_list.itemActivated.connect(self._load_series_item)
        lay.addWidget(self.series_list)
        dock.setWidget(w)
        dock.setMinimumWidth(240)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _build_report_dock(self):
        dock = QDockWidget("Laudo", self)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self.template_combo = QComboBox()
        for t in TEMPLATES:
            self.template_combo.addItem(t.title.title(), t)
        btn_load = QPushButton("Usar modelo")
        btn_load.clicked.connect(self._load_template)
        row.addWidget(self.template_combo, 1)
        row.addWidget(btn_load)
        lay.addLayout(row)

        self.report_edit = QPlainTextEdit()
        self.report_edit.setPlaceholderText("Escolha um modelo e clique em 'Usar modelo'.")
        lay.addWidget(self.report_edit, 1)

        tools = QHBoxLayout()
        for label, fn in [("ASPECTS", self._aspects), ("ABC/2", self._abc2),
                          ("Inserir medida", self._insert_measure)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            tools.addWidget(b)
        lay.addLayout(tools)
        btn_pdf = QPushButton("Exportar PDF")
        btn_pdf.setStyleSheet("font-weight:bold; padding:6px")
        btn_pdf.clicked.connect(self._export_pdf)
        lay.addWidget(btn_pdf)
        dock.setWidget(w)
        dock.setMinimumWidth(400)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _set_layout(self, mode: str):
        for v in self.viewers.values():
            self.grid.removeWidget(v)
            v.hide()
        if mode == "mpr":
            ax, co, sa = (self.viewers[p] for p in Plane)
            self.grid.addWidget(ax, 0, 0, 2, 1)
            self.grid.addWidget(co, 0, 1)
            self.grid.addWidget(sa, 1, 1)
            self.grid.setColumnStretch(0, 3)
            self.grid.setColumnStretch(1, 2)
            for v in (ax, co, sa):
                v.show()
        else:
            v = self.viewers[Plane(mode)]
            self.grid.addWidget(v, 0, 0, 2, 2)
            v.show()

    # ============================================================ dados
    def _ask_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Abrir pasta DICOM")
        if path:
            self.open_folder(path)

    def open_folder(self, path: str):
        self.statusBar().showMessage(f"Lendo {path}…")
        series = scan_folder(path)
        self.series_list.clear()
        if not series:
            QMessageBox.warning(self, "NeuroLaudo", "Nenhum arquivo DICOM encontrado.")
            return
        s0 = series[0]
        self.patient_label.setText(
            f"<b>{s0.patient_name}</b><br>ID {s0.patient_id} · {s0.patient_sex}<br>"
            f"{s0.study_description}<br>{s0.study_date}")
        for s in series:
            item = QListWidgetItem(s.label)
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.series_list.addItem(item)
        self.statusBar().showMessage(f"{len(series)} série(s) encontrada(s)")
        largest = max(series, key=lambda s: len(s.files))
        self.load_series(largest)

    def _load_series_item(self, item: QListWidgetItem):
        self.load_series(item.data(Qt.ItemDataRole.UserRole))

    def load_series(self, series: Series):
        try:
            self.volume = load_volume(series)
        except Exception as exc:  # noqa: BLE001 - mostrar qualquer erro de leitura ao usuário
            QMessageBox.critical(self, "Erro ao abrir série", str(exc))
            return
        if series.modality == "CT":
            c, w = self.volume.default_window or (40, 80)
        else:
            c, w = auto_window(self.volume.data)
        for v in self.viewers.values():
            v.set_volume(self.volume, c, w)
        z, y, x = self.volume.data.shape
        sz, sy, sx = self.volume.spacing
        self.statusBar().showMessage(
            f"{series.label} — matriz {x}×{y}×{z}, voxel {sx:.2f}×{sy:.2f}×{sz:.2f} mm")

    # ========================================================= ações
    def _set_tool(self, tool: Tool):
        for v in self.viewers.values():
            v.tool = tool

    def _apply_preset(self):
        data = self.preset_combo.currentData()
        if data and self.volume:
            self._sync_window(*data)

    def _apply_slab(self):
        for v in self.viewers.values():
            v.set_slab(self.slab_spin.value(), self.slab_combo.currentData())

    def _sync_window(self, c: float, w: float):
        for v in self.viewers.values():
            v.set_window(c, w)

    def _sync_cross(self, voxel):
        sender = self.sender()
        for v in self.viewers.values():
            v.set_cross(voxel, move_slice=v is not sender)

    def _on_measure(self, mm: float):
        self.last_measure_mm = mm
        self.statusBar().showMessage(f"Medida: {mm:.1f} mm")

    def _load_template(self):
        if self.report_edit.toPlainText().strip():
            r = QMessageBox.question(self, "Substituir laudo", "Substituir o texto atual pelo modelo?")
            if r != QMessageBox.StandardButton.Yes:
                return
        self.report_edit.setPlainText(render_text(self.template_combo.currentData()))

    def _replace_or_insert(self, placeholder: str, text: str):
        body = self.report_edit.toPlainText()
        if placeholder in body:
            self.report_edit.setPlainText(body.replace(placeholder, text))
        else:
            self.report_edit.insertPlainText(text)

    def _aspects(self):
        d = AspectsDialog(self)
        if d.exec():
            body = self.report_edit.toPlainText()
            if "ASPECTS" in body and "___" in body:
                self.report_edit.setPlainText(body.replace("ASPECTS: ___", f"ASPECTS: {d.text()}")
                                              .replace("ASPECTS ___", f"ASPECTS {d.score()}"))
            else:
                self.report_edit.insertPlainText(f"ASPECTS: {d.text()}.")

    def _abc2(self):
        d = Abc2Dialog(self, self.last_measure_mm)
        if d.exec():
            self.report_edit.insertPlainText(d.text())

    def _insert_measure(self):
        if self.last_measure_mm is None:
            QMessageBox.information(self, "Medida", "Faça uma medida com a ferramenta Régua.")
            return
        self.report_edit.insertPlainText(f"{self.last_measure_mm / 10:.1f} cm")

    def _export_pdf(self):
        body = self.report_edit.toPlainText().strip()
        if not body:
            QMessageBox.information(self, "Laudo", "O laudo está vazio.")
            return
        if "___" in body:
            r = QMessageBox.question(self, "Campos pendentes",
                                     "Há campos não preenchidos (___). Exportar mesmo assim?")
            if r != QMessageBox.StandardButton.Yes:
                return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar laudo", "laudo.pdf", "PDF (*.pdf)")
        if not path:
            return
        st = QSettings("NeuroLaudo", "NeuroLaudo")
        s = self.volume.series if self.volume else None
        header = ReportHeader(
            institution=st.value("institution", ""), physician=st.value("physician", ""),
            crm=st.value("crm", ""),
            patient_name=s.patient_name if s else "", patient_id=s.patient_id if s else "",
            exam_date=s.study_date if s else "", accession=s.accession if s else "")
        export_pdf(path, header, body)
        self.statusBar().showMessage(f"Laudo salvo em {path}")
