"""
Устанавливает модуль моделирования жидкости в проект SpeedSensor Lab.
Запуск: python install_fluid_sim.py <путь_к_speedsensor_app>
"""
import sys
import os
import shutil

FLUID_SIM_CODE = r'''"""
Вкладка «Моделирование жидкости» (🌊).

Сосуд: 200 × 100 × 40 мм, прямоугольный параллелепипед.
Ось вращения: центральная вертикальная вдоль длины 200 мм.
Поверхность жидкости: парабола h(x) = h_vertex + ω²x²/(2g)
  h_vertex подбирается из условия сохранения объёма жидкости.

Источник ω:
  - «Датчик»       — DataReaderThread (сигнал new_sample)
  - «Таблица»      — загружает CSV, воспроизводит с таймером
  - «Генерация»    — ручной ввод / слайдер для демонстрации
"""
import math
import csv

import numpy as np
import pyqtgraph as pg

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QFormLayout, QLabel, QDoubleSpinBox, QComboBox, QPushButton,
    QFileDialog, QTabWidget, QSlider, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from core.data_reader import DataReaderThread
from core.motor_sim import MotorSimModel

# ─────────────────────────── физика ──────────────────────────────────────────

G         = 9.80665
VESSEL_L  = 0.200   # м (длина, ось вращения)
VESSEL_W  = 0.040   # м (ширина)
VESSEL_H  = 0.100   # м (высота)
H0_DEFAULT = 0.075  # м
NX = 80
NY = 40


def parabola_vertex(omega: float, h0: float) -> float:
    """h_vertex при сохранении объёма: h_v = h0 - ω²L²/(24g)"""
    return h0 - (omega ** 2 * (VESSEL_L / 2) ** 2) / (24.0 * G)


def surface_height(x: float, omega: float, h0: float) -> float:
    hv = parabola_vertex(omega, h0)
    return max(0.0, min(hv + omega ** 2 * x ** 2 / (2.0 * G), VESSEL_H))


def surface_grid(omega: float, h0: float):
    xs = np.linspace(-VESSEL_L / 2, VESSEL_L / 2, NX)
    ys = np.linspace(-VESSEL_W / 2, VESSEL_W / 2, NY)
    hv = parabola_vertex(omega, h0)
    X, Y = np.meshgrid(xs, ys)
    Z = np.clip(hv + omega ** 2 * xs ** 2 / (2.0 * G), 0.0, VESSEL_H)
    Z2d = np.tile(Z, (NY, 1))
    return xs, ys, X, Y, Z2d.astype(np.float32)


# ─────────────────────────── константы ───────────────────────────────────────

SOURCE_SENSOR   = "sensor"
SOURCE_TABLE    = "table"
SOURCE_GENERATE = "generate"

SOURCE_LABELS = {
    SOURCE_GENERATE: "Генерация (демонстрация)",
    SOURCE_TABLE:    "CSV-таблица",
    SOURCE_SENSOR:   "Датчик (реальный / симуляция)",
}

C_BG   = "#1e1e2e"
C_TEXT = "#cdd6f4"


# ─────────────────────────── виджет ──────────────────────────────────────────

class FluidSimWidget(QWidget):
    """Вкладка моделирования жидкости во вращающемся сосуде."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._omega: float = 0.0
        self._h0: float = H0_DEFAULT
        self._source: str = SOURCE_GENERATE
        self._table_data: list[tuple[float, float]] = []
        self._table_idx: int = 0
        self._reader: DataReaderThread | None = None
        self._sim_model = MotorSimModel()

        self._viz_timer = QTimer(self)
        self._viz_timer.setInterval(40)
        self._viz_timer.timeout.connect(self._refresh_viz)

        self._table_timer = QTimer(self)
        self._table_timer.setInterval(100)
        self._table_timer.timeout.connect(self._table_tick)

        self._build_ui()
        self._update_2d(0.0)

    # ═══════════════════════════════════════════════════════════ build UI ══

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Левая панель ─────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(280)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.setSpacing(10)

        # Источник ω
        grp_src = QGroupBox("Источник ω")
        fs = QFormLayout(grp_src)

        self._cb_source = QComboBox()
        for key, label in SOURCE_LABELS.items():
            self._cb_source.addItem(label, key)
        self._cb_source.currentIndexChanged.connect(self._on_source_changed)
        fs.addRow("Источник:", self._cb_source)

        self._spin_omega = QDoubleSpinBox()
        self._spin_omega.setRange(0.0, 100.0)
        self._spin_omega.setDecimals(2)
        self._spin_omega.setSuffix(" рад/с")
        self._spin_omega.setSingleStep(0.5)
        self._spin_omega.valueChanged.connect(self._on_manual_omega)
        fs.addRow("ω:", self._spin_omega)

        self._slider_omega = QSlider(Qt.Orientation.Horizontal)
        self._slider_omega.setRange(0, 1000)
        self._slider_omega.valueChanged.connect(self._on_slider_omega)
        fs.addRow("Слайдер:", self._slider_omega)

        self._btn_load_csv = QPushButton("📂  Загрузить CSV")
        self._btn_load_csv.clicked.connect(self._on_load_csv)
        self._btn_load_csv.setVisible(False)
        fs.addRow(self._btn_load_csv)

        self._lbl_csv = QLabel("Файл не выбран")
        self._lbl_csv.setStyleSheet("color: #6c7086; font-size: 11px;")
        self._lbl_csv.setVisible(False)
        fs.addRow(self._lbl_csv)

        ll.addWidget(grp_src)

        # Параметры сосуда (фиксированные)
        grp_v = QGroupBox("Параметры сосуда")
        fv = QFormLayout(grp_v)
        for label, val in [("Длина (ось вращ.):", f"{int(VESSEL_L*1000)} мм"),
                            ("Ширина:",           f"{int(VESSEL_W*1000)} мм"),
                            ("Высота:",           f"{int(VESSEL_H*1000)} мм")]:
            lbl = QLabel(val)
            lbl.setStyleSheet("color: #a6adc8;")
            fv.addRow(label, lbl)

        self._spin_h0 = QDoubleSpinBox()
        self._spin_h0.setRange(5.0, 95.0)
        self._spin_h0.setDecimals(1)
        self._spin_h0.setSuffix(" мм")
        self._spin_h0.setValue(H0_DEFAULT * 1000)  # 75 мм
        self._spin_h0.valueChanged.connect(self._on_h0_changed)
        fv.addRow("Уровень h₀:", self._spin_h0)
        ll.addWidget(grp_v)

        # Текущие значения
        grp_r = QGroupBox("Текущие значения")
        fr = QFormLayout(grp_r)

        self._lbl_omega_val = QLabel("0.000 рад/с")
        self._lbl_omega_val.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._lbl_omega_val.setStyleSheet("color: #cba6f7;")
        fr.addRow("ω:", self._lbl_omega_val)

        self._lbl_hv = QLabel("—")
        self._lbl_hv.setStyleSheet("color: #89b4fa;")
        fr.addRow("h вершины:", self._lbl_hv)

        self._lbl_hmax = QLabel("—")
        self._lbl_hmax.setStyleSheet("color: #f38ba8;")
        fr.addRow("h на краю:", self._lbl_hmax)

        self._lbl_overflow = QLabel("")
        self._lbl_overflow.setStyleSheet("color: #f38ba8; font-weight: bold;")
        fr.addRow(self._lbl_overflow)
        ll.addWidget(grp_r)

        # Кнопки
        br = QHBoxLayout()
        self._btn_start = QPushButton("▶  Старт")
        self._btn_start.setProperty("class", "primary-btn")
        self._btn_start.clicked.connect(self._on_start)
        br.addWidget(self._btn_start)
        self._btn_stop = QPushButton("⏹  Стоп")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        br.addWidget(self._btn_stop)
        ll.addLayout(br)
        ll.addStretch()

        splitter.addWidget(left)

        # ── Правая: вкладки 2D / 3D ─────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 4, 4, 4)

        self._tabs_viz = QTabWidget()

        # 2D
        pg.setConfigOptions(antialias=True, background=C_BG, foreground=C_TEXT)
        self._plot2d = pg.PlotWidget()
        self._plot2d.setLabel("left", "Высота, мм")
        self._plot2d.setLabel("bottom", "x (от оси), мм")
        self._plot2d.showGrid(x=True, y=True, alpha=0.3)
        self._plot2d.setXRange(-VESSEL_L / 2 * 1000, VESSEL_L / 2 * 1000)
        self._plot2d.setYRange(0, VESSEL_H * 1000 * 1.15)
        self._plot2d.getAxis("left").setTextPen(C_TEXT)
        self._plot2d.getAxis("bottom").setTextPen(C_TEXT)

        # Нижняя нулевая кривая (для FillBetween)
        self._curve_bottom = self._plot2d.plot(
            np.linspace(-VESSEL_L/2*1000, VESSEL_L/2*1000, NX),
            np.zeros(NX), pen=None,
        )
        self._curve_surface = self._plot2d.plot(
            pen=pg.mkPen(color="#64b5f6", width=2.5)
        )
        self._fill_liquid = pg.FillBetweenItem(
            self._curve_surface, self._curve_bottom,
            brush=pg.mkBrush(64, 156, 255, 70),
        )
        self._plot2d.addItem(self._fill_liquid)

        # Стенки
        wall_pen = pg.mkPen(color="#585b70", width=2)
        xl, xr = -VESSEL_L/2*1000, VESSEL_L/2*1000
        hh = VESSEL_H * 1000
        self._plot2d.plot([xl, xl],  [0, hh], pen=wall_pen)
        self._plot2d.plot([xr, xr],  [0, hh], pen=wall_pen)
        self._plot2d.plot([xl, xr],  [0, 0],  pen=wall_pen)
        self._plot2d.plot([xl, xr],  [hh, hh],
                          pen=pg.mkPen(color="#585b70", width=1,
                                       style=Qt.PenStyle.DashLine))

        self._line_h0 = pg.InfiniteLine(
            angle=0, pos=H0_DEFAULT*1000,
            pen=pg.mkPen(color="#a6e3a1", width=1, style=Qt.PenStyle.DotLine),
            label="h₀", labelOpts={"color": "#a6e3a1", "position": 0.05},
        )
        self._plot2d.addItem(self._line_h0)

        # Перекрестие
        self._vline2d = pg.InfiniteLine(angle=90, movable=False,
            pen=pg.mkPen(color="#585b70", width=1, style=Qt.PenStyle.DashLine))
        self._hline2d = pg.InfiniteLine(angle=0, movable=False,
            pen=pg.mkPen(color="#585b70", width=1, style=Qt.PenStyle.DashLine))
        self._plot2d.addItem(self._vline2d, ignoreBounds=True)
        self._plot2d.addItem(self._hline2d, ignoreBounds=True)
        self._vline2d.setVisible(False)
        self._hline2d.setVisible(False)

        self._snap_dot2d = pg.ScatterPlotItem(
            size=9, pen=pg.mkPen(None), brush=pg.mkBrush("#a6e3a1"))
        self._plot2d.addItem(self._snap_dot2d)
        self._snap_dot2d.setVisible(False)

        self._lbl_tip2d = QLabel("", self._plot2d)
        self._lbl_tip2d.setStyleSheet(
            "background: rgba(30,30,46,210); color: #cdd6f4;"
            "border: 1px solid #cba6f7; border-radius: 6px;"
            "padding: 4px 8px; font-size: 11px; font-family: Consolas;")
        self._lbl_tip2d.hide()

        self._mouse_proxy2d = pg.SignalProxy(
            self._plot2d.scene().sigMouseMoved,
            rateLimit=30, slot=self._on_mouse_2d)

        self._tabs_viz.addTab(self._plot2d, "📐  2D сечение")

        # 3D
        self._has_3d = False
        try:
            import pyqtgraph.opengl as gl
            self._gl = gl
            self._view3d = gl.GLViewWidget()
            self._view3d.setBackgroundColor(C_BG)
            self._view3d.setCameraPosition(distance=0.38, elevation=28, azimuth=45)

            grid = gl.GLGridItem()
            grid.setSize(0.3, 0.2)
            grid.setSpacing(0.02, 0.02)
            self._view3d.addItem(grid)
            self._view3d.addItem(self._make_vessel_wireframe(gl))

            self._surf_item = gl.GLMeshItem(
                smooth=True,
                color=(0.25, 0.60, 1.0, 0.65),
                shader="balloon",
                glOptions="translucent",
            )
            self._view3d.addItem(self._surf_item)
            self._update_surface_3d(0.0)

            self._tabs_viz.addTab(self._view3d, "🌐  3D")
            self._has_3d = True
        except Exception:
            lbl3d = QLabel("3D требует PyOpenGL.\npip install PyOpenGL PyOpenGL_accelerate")
            lbl3d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl3d.setStyleSheet("color: #6c7086;")
            self._tabs_viz.addTab(lbl3d, "🌐  3D")

        rl.addWidget(self._tabs_viz)
        splitter.addWidget(right)
        splitter.setSizes([280, 800])
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    # ═══════════════════════════════════════════════════════════ 3D helpers ══

    def _make_vessel_wireframe(self, gl):
        L, W, H = VESSEL_L, VESSEL_W, VESSEL_H
        pts = np.array([
            [-L/2,-W/2, 0],[ L/2,-W/2, 0],[ L/2, W/2, 0],[-L/2, W/2, 0],
            [-L/2,-W/2, H],[ L/2,-W/2, H],[ L/2, W/2, H],[-L/2, W/2, H],
        ], dtype=np.float32)
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
                 (0,4),(1,5),(2,6),(3,7)]
        lines = np.array([[pts[a], pts[b]] for a,b in edges],
                         dtype=np.float32).reshape(-1, 3)
        return gl.GLLinePlotItem(pos=lines, color=(0.35, 0.35, 0.45, 0.8),
                                 width=1.5, mode="lines")

    def _update_surface_3d(self, omega: float):
        """
        Строит полный замкнутый объём жидкости:
          верхняя параболическая поверхность + дно + 4 боковые грани.
        """
        if not self._has_3d:
            return
        gl = self._gl
        xs, ys, X, Y, Z_top = surface_grid(omega, self._h0)

        verts = []
        faces = []

        # ── Верхняя поверхность (парабола) ───────────────────────────────
        top_base = 0
        for i in range(NY):
            for j in range(NX):
                verts.append([X[i,j], Y[i,j], float(Z_top[i,j])])
        for i in range(NY - 1):
            for j in range(NX - 1):
                a = top_base + i*NX + j
                b = a + 1
                c = top_base + (i+1)*NX + j
                d = c + 1
                faces += [[a,b,d],[a,d,c],[a,d,b],[a,c,d]]

        # ── Дно (z = 0) ──────────────────────────────────────────────────
        bot_base = len(verts)
        for i in range(NY):
            for j in range(NX):
                verts.append([X[i,j], Y[i,j], 0.0])
        for i in range(NY - 1):
            for j in range(NX - 1):
                a = bot_base + i*NX + j
                b = a + 1
                c = bot_base + (i+1)*NX + j
                d = c + 1
                faces += [[a,d,b],[a,c,d]]

        verts_np = np.array(verts, dtype=np.float32)

        # ── Боковые грани по X (x = -L/2 и x = +L/2) ────────────────────
        for ji in [0, NX-1]:
            for i in range(NY - 1):
                t0 = verts_np[top_base + i*NX     + ji].tolist()
                t1 = verts_np[top_base + (i+1)*NX + ji].tolist()
                b0 = verts_np[bot_base + i*NX     + ji].tolist()
                b1 = verts_np[bot_base + (i+1)*NX + ji].tolist()
                base = len(verts)
                verts += [t0, t1, b1, b0]
                faces += [[base,base+1,base+2],[base,base+2,base+3],
                           [base,base+2,base+1],[base,base+2,base+3]]

        # ── Боковые грани по Y (y = -W/2 и y = +W/2) ────────────────────
        for ii in [0, NY-1]:
            for j in range(NX - 1):
                t0 = verts_np[top_base + ii*NX + j  ].tolist()
                t1 = verts_np[top_base + ii*NX + j+1].tolist()
                b0 = verts_np[bot_base + ii*NX + j  ].tolist()
                b1 = verts_np[bot_base + ii*NX + j+1].tolist()
                base = len(verts)
                verts += [t0, t1, b1, b0]
                faces += [[base,base+1,base+2],[base,base+2,base+3],
                           [base,base+2,base+1],[base,base+2,base+3]]

        verts_final = np.array(verts, dtype=np.float32)
        faces_final = np.array(faces, dtype=np.uint32)
        md = gl.MeshData(vertexes=verts_final, faces=faces_final)
        self._surf_item.setMeshData(meshdata=md)

    # ═══════════════════════════════════════════════════════════ update 2D ══

    def _update_2d(self, omega: float):
        xs_m  = np.linspace(-VESSEL_L/2, VESSEL_L/2, NX)
        xs_mm = xs_m * 1000
        hv = parabola_vertex(omega, self._h0)
        zs = np.clip(hv + omega**2 * xs_m**2 / (2*G), 0.0, VESSEL_H) * 1000
        self._curve_surface.setData(xs_mm, zs)

        h_vertex_mm = max(0.0, hv) * 1000
        h_edge_mm   = surface_height(VESSEL_L/2, omega, self._h0) * 1000
        self._lbl_omega_val.setText(f"{omega:.3f} рад/с")
        self._lbl_hv.setText(f"{h_vertex_mm:.1f} мм")
        self._lbl_hmax.setText(f"{h_edge_mm:.1f} мм")
        overflow = h_edge_mm >= VESSEL_H * 1000 * 0.99
        self._lbl_overflow.setText("⚠ Жидкость переливается!" if overflow else "")

    def _refresh_viz(self):
        self._update_2d(self._omega)
        if self._has_3d and self._tabs_viz.currentIndex() == 1:
            self._update_surface_3d(self._omega)

    # ═══════════════════════════════════════════════════════════ mouse 2D ══

    def _on_mouse_2d(self, evt):
        pos = evt[0]
        pw = self._plot2d
        if not pw.sceneBoundingRect().contains(pos):
            self._vline2d.setVisible(False)
            self._hline2d.setVisible(False)
            self._snap_dot2d.setVisible(False)
            self._lbl_tip2d.hide()
            return
        mp = pw.getPlotItem().vb.mapSceneToView(pos)
        x_mm = mp.x()
        x_m  = x_mm / 1000.0
        h_mm = surface_height(x_m, self._omega, self._h0) * 1000
        self._vline2d.setPos(x_mm)
        self._hline2d.setPos(h_mm)
        self._vline2d.setVisible(True)
        self._hline2d.setVisible(True)
        self._snap_dot2d.setData([x_mm], [h_mm])
        self._snap_dot2d.setVisible(True)

        self._lbl_tip2d.setText(
            f"x = {x_mm:.1f} мм\nh = {h_mm:.3f} мм\nω = {self._omega:.3f} рад/с")
        self._lbl_tip2d.adjustSize()
        sr = pw.sceneBoundingRect()
        tx, ty = pos.x()+14, pos.y()-10
        tw, th = self._lbl_tip2d.width(), self._lbl_tip2d.height()
        if tx+tw > sr.right()-4: tx = pos.x()-tw-14
        if ty+th > sr.bottom()-4: ty = pos.y()-th-4
        self._lbl_tip2d.move(int(tx), int(ty))
        self._lbl_tip2d.show()

    # ═══════════════════════════════════════════════════════════ controls ══

    def _on_source_changed(self):
        self._source = self._cb_source.currentData()
        is_table   = self._source == SOURCE_TABLE
        is_manual  = self._source == SOURCE_GENERATE
        self._spin_omega.setEnabled(is_manual)
        self._slider_omega.setEnabled(is_manual)
        self._btn_load_csv.setVisible(is_table)
        self._lbl_csv.setVisible(is_table)

    def _on_manual_omega(self, val: float):
        if self._source != SOURCE_GENERATE:
            return
        self._omega = val
        self._slider_omega.blockSignals(True)
        self._slider_omega.setValue(int(val * 10))
        self._slider_omega.blockSignals(False)
        if not self._viz_timer.isActive():
            self._update_2d(self._omega)

    def _on_slider_omega(self, val: int):
        if self._source != SOURCE_GENERATE:
            return
        omega = val / 10.0
        self._spin_omega.blockSignals(True)
        self._spin_omega.setValue(omega)
        self._spin_omega.blockSignals(False)
        self._omega = omega
        if not self._viz_timer.isActive():
            self._update_2d(self._omega)

    def _on_h0_changed(self, val: float):
        self._h0 = val / 1000.0
        self._line_h0.setValue(val)
        if not self._viz_timer.isActive():
            self._update_2d(self._omega)

    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть CSV", "", "CSV файлы (*.csv);;Все файлы (*)")
        if not path:
            return
        data = []
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                sample = f.read(2048)
            delim = ";" if sample.count(";") > sample.count(",") else ","
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=delim)
                for row in reader:
                    vals = list(row.values())
                    try:
                        data.append((float(vals[0]), float(vals[1])))
                    except (ValueError, IndexError):
                        pass
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить CSV:\n{e}")
            return
        if not data:
            QMessageBox.warning(self, "Ошибка", "CSV не содержит данных.")
            return
        self._table_data = data
        self._table_idx = 0
        fname = path.replace("\\", "/").split("/")[-1]
        self._lbl_csv.setText(f"✓ {fname} ({len(data)} строк)")

    # ═══════════════════════════════════════════════════════════ start/stop ══

    def _on_start(self):
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._viz_timer.start()

        if self._source == SOURCE_TABLE:
            if not self._table_data:
                QMessageBox.warning(self, "Нет данных", "Сначала загрузите CSV.")
                self._on_stop()
                return
            self._table_idx = 0
            self._table_timer.start()

        elif self._source == SOURCE_SENSOR:
            self._reader = DataReaderThread()
            self._reader.configure_sim(self._sim_model, sample_rate_hz=20)
            self._reader.new_sample.connect(
                self._on_sensor_sample, Qt.ConnectionType.QueuedConnection)
            self._reader.start()

    def _on_stop(self):
        self._viz_timer.stop()
        self._table_timer.stop()
        if self._reader:
            self._reader.stop()
            self._reader = None
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _on_sensor_sample(self, t: float, omega: float):
        self._omega = omega

    def _table_tick(self):
        if not self._table_data:
            return
        _, omega = self._table_data[self._table_idx % len(self._table_data)]
        self._omega = omega
        self._table_idx += 1

    def set_omega(self, omega: float):
        """Внешний вызов — передать ω от эксперимента."""
        self._omega = omega
'''


MAIN_WINDOW_OLD = '''        # Остальные вкладки-заглушки
        self._tabs.addTab(self._make_placeholder("Обработка данных"), "🔬  Обработка")
        self._tabs.addTab(self._make_placeholder("Моделирование жидкости"), "🌊  Моделирование")'''

MAIN_WINDOW_NEW = '''        # Вкладка обработки (заглушка)
        self._tabs.addTab(self._make_placeholder("Обработка данных"), "🔬  Обработка")

        # Вкладка моделирования жидкости
        from ui.fluid_sim_widget import FluidSimWidget
        self._fluid_sim = FluidSimWidget()
        self._tabs.addTab(self._fluid_sim, "🌊  Моделирование")'''


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  WRITTEN: {path}")


def patch_file(path, old, new):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if old not in content:
        print(f"  SKIP (маркер не найден): {path}")
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.replace(old, new, 1))
    print(f"  PATCHED: {path}")
    return True


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "."

    # 1. Записать fluid_sim_widget.py
    write_file(os.path.join(base, "ui", "fluid_sim_widget.py"), FLUID_SIM_CODE)

    # 2. Подключить в main_window.py
    mw_path = os.path.join(base, "ui", "main_window.py")
    ok = patch_file(mw_path, MAIN_WINDOW_OLD, MAIN_WINDOW_NEW)
    if not ok:
        print("  WARN: main_window.py уже содержит fluid_sim или изменился — проверьте вручную")

    # 3. Обновить названия вкладок в _on_lang_changed
    patch_file(
        mw_path,
        '        tab_ru = ["📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]\n'
        '        tab_en = ["📋  Scenarios", "📈  Experiment",  "🔬  Processing", "🌊  Simulation"]',
        '        tab_ru = ["📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]\n'
        '        tab_en = ["📋  Scenarios", "📈  Experiment",  "🔬  Processing", "🌊  Fluid Sim"]',
    )

    print("\nГотово.")
    print("Дополнительно для 3D:")
    print("  pip install PyOpenGL PyOpenGL_accelerate")


if __name__ == "__main__":
    main()
