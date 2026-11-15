"""Widget de visualização de um plano (axial/coronal/sagital) com ferramentas básicas."""
from __future__ import annotations

from enum import Enum

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from neurolaudo.dicom.loader import Volume
from neurolaudo.imaging import mpr
from neurolaudo.imaging.mpr import Plane
from neurolaudo.imaging.windowing import apply_window


class Tool(str, Enum):
    WINDOW = "Janela (W/L)"
    MEASURE = "Régua"
    CROSSHAIR = "Localizar"
    PAN_ZOOM = "Mover/Zoom"


class SliceViewer(QWidget):
    windowChanged = Signal(float, float)
    voxelPicked = Signal(tuple)          # (z, y, x)
    measured = Signal(float)             # distância em mm

    def __init__(self, plane: Plane, parent=None):
        super().__init__(parent)
        self.plane = plane
        self.volume: Volume | None = None
        self.index = 0
        self.center, self.width_ = 40.0, 80.0
        self.thickness = 1
        self.proj_mode = "avg"
        self.tool = Tool.WINDOW
        self.zoom, self.pan = 1.0, QPointF(0, 0)
        self.cross: tuple[int, int, int] | None = None
        self.rulers: dict[int, list[tuple[QPointF, QPointF]]] = {}
        self._drag_start = None
        self._drag_button = None
        self._ruler_tmp: tuple[QPointF, QPointF] | None = None
        self._cursor_info = ""
        self._qimage = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(200, 200)

    # ------------------------------------------------------------------ dados
    def set_volume(self, vol: Volume, center: float, width: float):
        self.volume = vol
        self.center, self.width_ = center, width
        self.index = mpr.n_slices(vol.data.shape, self.plane) // 2
        self.rulers.clear()
        self.cross = None
        self.reset_view()

    def set_window(self, center: float, width: float):
        self.center, self.width_ = center, max(width, 1.0)
        self.update()

    def set_slab(self, thickness: int, mode: str):
        self.thickness, self.proj_mode = max(1, thickness), mode
        self.update()

    def reset_view(self):
        self.zoom, self.pan = 1.0, QPointF(0, 0)
        self.update()

    def set_cross(self, voxel: tuple[int, int, int], move_slice: bool = True):
        self.cross = voxel
        if move_slice:
            self.index = mpr.from_voxel(self.plane, voxel)
        self.update()

    def n_slices(self) -> int:
        return mpr.n_slices(self.volume.data.shape, self.plane) if self.volume else 0

    def scroll(self, delta: int):
        if not self.volume:
            return
        self.index = int(np.clip(self.index + delta, 0, self.n_slices() - 1))
        self.update()

    # ----------------------------------------------------------- geometria
    def _image(self) -> np.ndarray:
        return mpr.get_slice(self.volume.data, self.plane, self.index, self.thickness, self.proj_mode)

    def _target_rect(self, img_shape) -> QRectF:
        rows, cols = img_shape
        dr, dc = mpr.pixel_spacing(self.volume.spacing, self.plane)
        phys_w, phys_h = cols * dc, rows * dr
        scale = min(self.width() / phys_w, self.height() / phys_h) * self.zoom
        w, h = phys_w * scale, phys_h * scale
        x = (self.width() - w) / 2 + self.pan.x()
        y = (self.height() - h) / 2 + self.pan.y()
        return QRectF(x, y, w, h)

    def _to_image(self, pos: QPointF, img_shape) -> tuple[float, float] | None:
        r = self._target_rect(img_shape)
        rows, cols = img_shape
        if not r.contains(pos):
            return None
        col = (pos.x() - r.x()) / r.width() * cols
        row = (pos.y() - r.y()) / r.height() * rows
        return row, col

    def _to_screen(self, row: float, col: float, img_shape) -> QPointF:
        r = self._target_rect(img_shape)
        rows, cols = img_shape
        return QPointF(r.x() + col / cols * r.width(), r.y() + row / rows * r.height())

    def _distance_mm(self, a: QPointF, b: QPointF) -> float:
        dr, dc = mpr.pixel_spacing(self.volume.spacing, self.plane)
        return float(np.hypot((a.x() - b.x()) * dr, (a.y() - b.y()) * dc))

    # -------------------------------------------------------------- pintura
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        if not self.volume:
            p.setPen(QColor("#777"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self.plane.value}\n(abra uma série)")
            return
        img = self._image()
        u8 = apply_window(img, self.center, self.width_)
        h, w = u8.shape
        self._qimage = QImage(u8.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
        target = self._target_rect(u8.shape)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawImage(target, self._qimage)

        # cruz de localização
        if self.cross is not None:
            vz, vy, vx = self.cross
            z = self.volume.data.shape[0]
            if self.plane == Plane.AXIAL:
                rc = (vy, vx)
            elif self.plane == Plane.CORONAL:
                rc = (z - 1 - vz, vx)
            else:
                rc = (z - 1 - vz, vy)
            pt = self._to_screen(rc[0] + 0.5, rc[1] + 0.5, u8.shape)
            p.setPen(QPen(QColor(255, 200, 0, 160), 1))
            p.drawLine(QPointF(target.left(), pt.y()), QPointF(target.right(), pt.y()))
            p.drawLine(QPointF(pt.x(), target.top()), QPointF(pt.x(), target.bottom()))

        # réguas
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rulers = list(self.rulers.get(self.index, []))
        if self._ruler_tmp:
            rulers.append(self._ruler_tmp)
        p.setFont(QFont("Helvetica", 10))
        for a, b in rulers:
            sa, sb = self._to_screen(a.x(), a.y(), u8.shape), self._to_screen(b.x(), b.y(), u8.shape)
            p.setPen(QPen(QColor("#33ff66"), 1.5))
            p.drawLine(sa, sb)
            p.drawText(sb + QPointF(6, -6), f"{self._distance_mm(a, b):.1f} mm")

        # textos de sobreposição
        p.setPen(QColor("#e0e0e0"))
        s = self.volume.series
        p.drawText(8, 16, f"{self.plane.value}  {self.index + 1}/{self.n_slices()}")
        if self.thickness > 1:
            p.drawText(8, 32, f"Slab {self.proj_mode.upper()} {self.thickness} cortes")
        p.drawText(8, self.height() - 10, f"C {self.center:.0f}  L {self.width_:.0f}   {self._cursor_info}")
        fm = p.fontMetrics()
        txt = s.patient_name
        p.drawText(self.width() - fm.horizontalAdvance(txt) - 8, 16, txt)
        # marcadores de orientação (convenção radiológica)
        labels = {Plane.AXIAL: ("A", "P", "D", "E"), Plane.CORONAL: ("S", "I", "D", "E"),
                  Plane.SAGITTAL: ("S", "I", "A", "P")}[self.plane]
        p.setPen(QColor("#ffcc66"))
        p.drawText(int(self.width() / 2), 30, labels[0])
        p.drawText(int(self.width() / 2), self.height() - 24, labels[1])
        p.drawText(8, int(self.height() / 2), labels[2])
        p.drawText(self.width() - 16, int(self.height() / 2), labels[3])

    # -------------------------------------------------------------- eventos
    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom *= 1.1 if ev.angleDelta().y() > 0 else 1 / 1.1
            self.update()
        else:
            self.scroll(1 if ev.angleDelta().y() > 0 else -1)

    def keyPressEvent(self, ev):
        k = ev.key()
        if k in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
            self.scroll(1)
        elif k in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
            self.scroll(-1)
        elif k == Qt.Key.Key_Delete:
            self.rulers.pop(self.index, None)
            self.update()
        else:
            super().keyPressEvent(ev)

    def mousePressEvent(self, ev):
        if not self.volume:
            return
        self._drag_start = ev.position()
        self._drag_button = ev.button()
        self._start_window = (self.center, self.width_)
        self._start_pan, self._start_zoom = QPointF(self.pan), self.zoom
        img_shape = self._image().shape
        tool = self.tool if ev.button() == Qt.MouseButton.LeftButton else Tool.WINDOW
        if ev.button() == Qt.MouseButton.MiddleButton:
            tool = Tool.PAN_ZOOM
        self._active_tool = tool
        if tool == Tool.MEASURE:
            rc = self._to_image(ev.position(), img_shape)
            if rc:
                pt = QPointF(rc[0], rc[1])
                self._ruler_tmp = (pt, pt)
        elif tool == Tool.CROSSHAIR:
            self._pick(ev.position(), img_shape)

    def _pick(self, pos, img_shape):
        rc = self._to_image(pos, img_shape)
        if rc:
            vox = mpr.to_voxel(self.plane, self.index, rc[0], rc[1], self.volume.data.shape)
            self.voxelPicked.emit(vox)

    def mouseMoveEvent(self, ev):
        if not self.volume:
            return
        img = self._image()
        rc = self._to_image(ev.position(), img.shape)
        if rc:
            r, c = int(rc[0]), int(rc[1])
            unit = " HU" if self.volume.series.modality == "CT" else ""
            self._cursor_info = f"[{c},{r}] {img[r, c]:.0f}{unit}"
        else:
            self._cursor_info = ""
        if self._drag_start is None:
            self.update()
            return
        d = ev.position() - self._drag_start
        tool = self._active_tool
        if tool == Tool.WINDOW:
            c0, w0 = self._start_window
            self.set_window(c0 - d.y() * max(w0, 10) / 200, max(1.0, w0 + d.x() * max(w0, 10) / 200))
            self.windowChanged.emit(self.center, self.width_)
        elif tool == Tool.MEASURE and self._ruler_tmp and rc:
            self._ruler_tmp = (self._ruler_tmp[0], QPointF(rc[0], rc[1]))
        elif tool == Tool.CROSSHAIR:
            self._pick(ev.position(), img.shape)
        elif tool == Tool.PAN_ZOOM:
            if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.zoom = max(0.2, self._start_zoom * (1 - d.y() / 200))
            else:
                self.pan = self._start_pan + d
        self.update()

    def mouseReleaseEvent(self, _ev):
        if self._ruler_tmp:
            a, b = self._ruler_tmp
            if (a - b).manhattanLength() > 0.5:
                self.rulers.setdefault(self.index, []).append(self._ruler_tmp)
                self.measured.emit(self._distance_mm(a, b))
            self._ruler_tmp = None
        self._drag_start = None
        self.update()

    def mouseDoubleClickEvent(self, _ev):
        self.reset_view()
