"""
Вкладка эксперимента.
Режим (симуляция / реальный датчик) задаётся снаружи через setup().
"""
import math
from collections import deque
import numpy as np
import pyqtgraph as pg

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QPushButton, QLabel, QComboBox, QSpinBox, QTabWidget, QFrame, QCheckBox,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QColorDialog, QGroupBox,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen

from core.motor_sim import MotorSimModel
from core.data_reader import DataReaderThread
from core.experiment_data import ExperimentData, DataRow
from ui.sim_settings_panel import SimSettingsPanel
from ui.widgets.data_table import DataTableWidget
from scenarios.scenarios import Scenario, UNIT_RAD_S, UNIT_RPS
from ui.mode_selector import MODE_SENSOR, MODE_SIMULATION

C_BG     = "#1e1e2e"
C_LINE   = "#cba6f7"
C_LINE2  = "#89b4fa"
C_TEXT   = "#cdd6f4"
C_ACCENT = "#a6e3a1"
MAX_POINTS = 5000



class _GraphTooltip(QWidget):
    """Полупрозрачное плавающее окошко с мгновенными значениями."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)

        self._labels: list[QLabel] = []
        for _ in range(5):
            lbl = QLabel("")
            lbl.setStyleSheet(
                "color: #cdd6f4; font-size: 11px; font-family: 'Consolas', monospace;"
                "background: transparent;"
            )
            lay.addWidget(lbl)
            self._labels.append(lbl)

        self.adjustSize()

    def update_text(self, lines: list[str]):
        for i, lbl in enumerate(self._labels):
            lbl.setText(lines[i] if i < len(lines) else "")
        self.adjustSize()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#1e1e2e")
        bg.setAlpha(210)
        p.setBrush(bg)
        border = QColor("#cba6f7")
        border.setAlpha(180)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 7, 7)


def _vsep() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    sep.setStyleSheet("color: #45475a;")
    return sep



# Словарь: отображаемое имя → Qt.PenStyle
_LINE_STYLES = {
    "Сплошная":         Qt.PenStyle.SolidLine,
    "Пунктир":          Qt.PenStyle.DashLine,
    "Точки":            Qt.PenStyle.DotLine,
    "Точка-пунктир":    Qt.PenStyle.DashDotLine,
    "2 точки-пунктир":  Qt.PenStyle.DashDotDotLine,
}

# Scatter-символы pyqtgraph (имя → symbol)
_SCATTER_STYLES = {
    "Круги":    "o",
    "Квадраты": "s",
    "Треугольники": "t",
    "Ромбы":    "d",
    "Кресты":   "+",
}


class _LineStyleDialog(QDialog):
    """Диалог настройки внешнего вида линии графика."""

    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка линии графика")
        self.setMinimumWidth(340)
        self._color = QColor(current.get("color", C_LINE))
        self._result = dict(current)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ── Цвет ──
        grp_color = QGroupBox("Цвет линии")
        cl = QHBoxLayout(grp_color)
        self._btn_color = QPushButton()
        self._btn_color.setFixedSize(80, 28)
        self._update_color_btn()
        self._btn_color.clicked.connect(self._pick_color)
        cl.addWidget(self._btn_color)
        cl.addStretch()
        lay.addWidget(grp_color)

        # ── Толщина ──
        grp_width = QGroupBox("Толщина линии")
        wl = QHBoxLayout(grp_width)
        self._spin_width = QDoubleSpinBox()
        self._spin_width.setRange(0.5, 10.0)
        self._spin_width.setSingleStep(0.5)
        self._spin_width.setValue(current.get("width", 2.0))
        self._spin_width.setSuffix(" px")
        wl.addWidget(self._spin_width)
        wl.addStretch()
        lay.addWidget(grp_width)

        # ── Тип линии ──
        grp_style = QGroupBox("Тип линии")
        sl = QHBoxLayout(grp_style)
        self._cb_style = QComboBox()
        for name in _LINE_STYLES:
            self._cb_style.addItem(name)
        cur_style = current.get("style", Qt.PenStyle.SolidLine)
        for i, s in enumerate(_LINE_STYLES.values()):
            if s == cur_style:
                self._cb_style.setCurrentIndex(i)
                break
        sl.addWidget(self._cb_style)
        lay.addWidget(grp_style)

        # ── Scatter поверх линии ──
        grp_sym = QGroupBox("Маркеры точек")
        syl = QHBoxLayout(grp_sym)
        self._cb_sym = QComboBox()
        self._cb_sym.addItem("Нет", None)
        for name, sym in _SCATTER_STYLES.items():
            self._cb_sym.addItem(name, sym)
        cur_sym = current.get("symbol", None)
        for i in range(self._cb_sym.count()):
            if self._cb_sym.itemData(i) == cur_sym:
                self._cb_sym.setCurrentIndex(i)
                break
        self._spin_sym_size = QDoubleSpinBox()
        self._spin_sym_size.setRange(2, 20)
        self._spin_sym_size.setValue(current.get("symbol_size", 6.0))
        self._spin_sym_size.setSuffix(" px")
        syl.addWidget(self._cb_sym)
        syl.addWidget(QLabel("размер:"))
        syl.addWidget(self._spin_sym_size)
        lay.addWidget(grp_sym)

        # ── Кнопки ──
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _update_color_btn(self):
        self._btn_color.setStyleSheet(
            f"background: {self._color.name()}; border: 1px solid #45475a; border-radius: 4px;"
        )
        self._btn_color.setText(self._color.name())

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Выберите цвет линии")
        if c.isValid():
            self._color = c
            self._update_color_btn()

    def _on_accept(self):
        self._result = {
            "color":       self._color.name(),
            "width":       self._spin_width.value(),
            "style":       list(_LINE_STYLES.values())[self._cb_style.currentIndex()],
            "symbol":      self._cb_sym.currentData(),
            "symbol_size": self._spin_sym_size.value(),
        }
        self.accept()

    def result_params(self) -> dict:
        return self._result


class ExperimentWidget(QWidget):
    # Запрос вернуться к экрану выбора режима
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scenario: Scenario | None = None
        self._sim_model = MotorSimModel()
        self._reader: DataReaderThread | None = None
        self._running = False

        self._mode: str = MODE_SIMULATION
        self._serial_port: str = ""
        self._serial_baud: int = 115200

        self._t_buf = deque(maxlen=MAX_POINTS)
        self._y_buf = deque(maxlen=MAX_POINTS)
        self._unit = UNIT_RAD_S
        self._exp_data = ExperimentData()
        # Кешированные numpy-массивы, обновляются только при новых данных
        self._t_cache: np.ndarray = np.empty(0)
        self._y_cache: np.ndarray = np.empty(0)   # в текущих единицах
        self._y_raw_cache: np.ndarray = np.empty(0)  # всегда rad/s
        self._cache_dirty: bool = False
        self._last_sample_count: int = 0
        self._zoom_x = True
        self._zoom_y = True
        self._line_params = {
            "color": C_LINE,
            "width": 2.0,
            "style": Qt.PenStyle.SolidLine,
            "symbol": None,
            "symbol_size": 6.0,
        }

        self._build_ui()
        self._setup_graph()

    # ================================================================= UI ==

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Верхняя строка: режим + кнопка смены
        top_row = QHBoxLayout()

        self._lbl_mode = QLabel()
        self._lbl_mode.setStyleSheet("color: #a6adc8; font-size: 12px;")
        top_row.addWidget(self._lbl_mode)

        top_row.addStretch()

        btn_change_mode = QPushButton("↩  Сменить режим")
        btn_change_mode.setFixedHeight(26)
        btn_change_mode.clicked.connect(self._on_back)
        top_row.addWidget(btn_change_mode)

        root.addLayout(top_row)

        # Сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Левая: симуляция (только в sim-режиме) ──────────────────────
        self._left = QWidget()
        self._left.setMinimumWidth(260)
        self._left.setMaximumWidth(320)
        left_lay = QVBoxLayout(self._left)
        left_lay.setContentsMargins(4, 4, 4, 4)
        left_lay.setSpacing(8)

        lbl_sim = QLabel("Моделирование эксперимента")
        lbl_sim.setProperty("class", "section-title")
        left_lay.addWidget(lbl_sim)

        self._sim_panel = SimSettingsPanel(self._sim_model)
        left_lay.addWidget(self._sim_panel)
        splitter.addWidget(self._left)

        # ── Правая: управление + граф/таблица ───────────────────────────
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(4, 4, 4, 4)
        right_lay.setSpacing(6)

        # Toolbar
        ctrl = QHBoxLayout()
        self._btn_start = QPushButton("▶  Старт")
        self._btn_start.setProperty("class", "primary-btn")
        self._btn_start.clicked.connect(self._on_start)
        ctrl.addWidget(self._btn_start)

        self._btn_stop_exp = QPushButton("⏹  Стоп")
        self._btn_stop_exp.setEnabled(False)
        self._btn_stop_exp.clicked.connect(self._on_stop)
        ctrl.addWidget(self._btn_stop_exp)

        self._btn_clear = QPushButton("🗑  Очистить")
        self._btn_clear.clicked.connect(self._on_clear)
        ctrl.addWidget(self._btn_clear)

        ctrl.addStretch()

        ctrl.addWidget(QLabel("Единицы:"))
        self._cb_unit = QComboBox()
        self._cb_unit.addItem("рад/с", UNIT_RAD_S)
        self._cb_unit.addItem("об/с", UNIT_RPS)
        self._cb_unit.currentIndexChanged.connect(self._on_unit_changed)
        ctrl.addWidget(self._cb_unit)

        ctrl.addWidget(QLabel("Окно:"))
        self._spin_window = QSpinBox()
        self._spin_window.setRange(5, 300)
        self._spin_window.setValue(30)
        self._spin_window.setSuffix(" с")
        ctrl.addWidget(self._spin_window)

        ctrl.addWidget(_vsep())

        self._chk_zoom_x = QCheckBox("Масштаб X")
        self._chk_zoom_x.setChecked(True)
        self._chk_zoom_x.setToolTip("Разрешить масштабирование по оси времени (X)")
        self._chk_zoom_x.stateChanged.connect(self._on_zoom_axes_changed)
        ctrl.addWidget(self._chk_zoom_x)

        self._chk_zoom_y = QCheckBox("Масштаб Y")
        self._chk_zoom_y.setChecked(True)
        self._chk_zoom_y.setToolTip("Разрешить масштабирование по оси значений (Y)")
        self._chk_zoom_y.stateChanged.connect(self._on_zoom_axes_changed)
        ctrl.addWidget(self._chk_zoom_y)

        ctrl.addWidget(_vsep())

        self._btn_line_style = QPushButton("🖊  Вид линии")
        self._btn_line_style.setToolTip("Настроить цвет, толщину и тип линии графика")
        self._btn_line_style.clicked.connect(self._on_line_style)
        ctrl.addWidget(self._btn_line_style)

        right_lay.addLayout(ctrl)

        # Текущее значение
        self._lbl_current = QLabel("— —")
        self._lbl_current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_current.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self._lbl_current.setStyleSheet(f"color: {C_ACCENT};")
        self._lbl_current.setFixedHeight(52)
        right_lay.addWidget(self._lbl_current)

        # Вкладки: График / Таблица
        self._inner_tabs = QTabWidget()
        pg.setConfigOptions(antialias=True, background=C_BG, foreground=C_TEXT)
        self._plot_widget = pg.PlotWidget()
        self._inner_tabs.addTab(self._plot_widget, "📈  График")
        self._table_widget = DataTableWidget(self._exp_data)
        self._inner_tabs.addTab(self._table_widget, "📋  Таблица")
        right_lay.addWidget(self._inner_tabs, 1)

        splitter.addWidget(right)
        splitter.setSizes([280, 720])
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    def _setup_graph(self):
        pw = self._plot_widget
        pw.setLabel("left", "ω, рад/с")
        pw.setLabel("bottom", "t, с")
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.getAxis("left").setTextPen(C_TEXT)
        pw.getAxis("bottom").setTextPen(C_TEXT)
        self._curve = pw.plot(
            pen=pg.mkPen(
                color=self._line_params["color"],
                width=self._line_params["width"],
                style=self._line_params["style"],
            )
        )
        self._setpoint_line = pg.InfiniteLine(
            angle=0, pos=0,
            pen=pg.mkPen(color=C_LINE2, width=1, style=Qt.PenStyle.DashLine),
            label="уставка",
            labelOpts={"color": C_LINE2, "position": 0.95},
        )
        pw.addItem(self._setpoint_line)
        self._setpoint_line.setVisible(False)

        # Перекрестие
        self._vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen(color="#585b70", width=1, style=Qt.PenStyle.DashLine),
        )
        self._hline = pg.InfiniteLine(
            angle=0, movable=False,
            pen=pg.mkPen(color="#585b70", width=1, style=Qt.PenStyle.DashLine),
        )
        pw.addItem(self._vline, ignoreBounds=True)
        pw.addItem(self._hline, ignoreBounds=True)
        self._vline.setVisible(False)
        self._hline.setVisible(False)

        # Плавающий tooltip поверх графика
        self._tooltip = _GraphTooltip(pw)
        self._tooltip.hide()

        # Точка на кривой
        self._snap_dot = pg.ScatterPlotItem(
            size=10, pen=pg.mkPen(None),
            brush=pg.mkBrush(C_ACCENT),
        )
        pw.addItem(self._snap_dot)
        self._snap_dot.setVisible(False)

        # Подключить сигнал мыши через proxy (rate-limit)
        self._mouse_proxy = pg.SignalProxy(
            pw.scene().sigMouseMoved,
            rateLimit=30,
            slot=self._on_mouse_move,
        )

        # Настроить разрешение масштабирования по осям (по умолчанию обе включены)
        pw.getPlotItem().vb.setMouseEnabled(x=True, y=True)

        # Убрать tooltip при выходе мыши
        pw.scene().sigMouseHover.connect(self._on_mouse_hover)

    # ============================================================== setup ==

    def setup(self, mode: str, port: str = "", baud: int = 115200,
              scenario: Scenario | None = None):
        """Вызывается перед показом вкладки."""
        self._mode = mode
        self._serial_port = port
        self._serial_baud = baud
        if scenario:
            self._scenario = scenario
            self._sim_model.slots = scenario.sensor.slots
            self._sim_model.disk_diameter_mm = scenario.sensor.disk_diameter_mm
            self._exp_data.disk_diameter_mm = scenario.sensor.disk_diameter_mm
            self._unit = scenario.unit
            idx = self._cb_unit.findData(self._unit)
            if idx >= 0:
                self._cb_unit.setCurrentIndex(idx)

        is_sim = (mode == MODE_SIMULATION)
        self._left.setVisible(is_sim)
        self._setpoint_line.setVisible(False)

        if is_sim:
            self._lbl_mode.setText("Режим: 🧪 Моделирование эксперимента")
        else:
            self._lbl_mode.setText(f"Режим: 🔌 Реальный датчик  |  {port}")

    # ========================================================= experiment ==

    def _on_start(self):
        if self._running:
            return
        self._on_clear()
        self._running = True
        self._btn_start.setEnabled(False)
        self._btn_stop_exp.setEnabled(True)

        sample_rate = self._scenario.sensor.sample_rate_hz if self._scenario else 50

        self._reader = DataReaderThread()
        if self._mode == MODE_SIMULATION:
            self._reader.configure_sim(self._sim_model, sample_rate_hz=sample_rate)
        else:
            self._reader.configure_serial(
                self._serial_port, self._serial_baud,
                sample_rate_hz=sample_rate,
            )

        self._reader.new_sample.connect(
            self._on_sample, Qt.ConnectionType.QueuedConnection
        )
        self._reader.error.connect(
            self._on_error, Qt.ConnectionType.QueuedConnection
        )
        self._reader.start()

        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._refresh_plot)
        self._timer.start()

    def _on_stop(self):
        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_stop_exp.setEnabled(False)
        if self._reader:
            self._reader.stop()
            self._reader = None
        if hasattr(self, "_timer"):
            self._timer.stop()

    def _on_clear(self):
        self._t_buf.clear()
        self._y_buf.clear()
        self._exp_data.clear()
        self._curve.setData([], [])
        self._t_cache = np.empty(0)
        self._y_cache = np.empty(0)
        self._y_raw_cache = np.empty(0)
        self._cache_dirty = False
        self._last_sample_count = 0
        self._lbl_current.setText("— —")
        self._table_widget._displayed_rows = 0
        self._table_widget._table.setRowCount(0)
        self._table_widget._lbl_count.setText("Записей: 0")

    def _on_unit_changed(self):
        self._unit = self._cb_unit.currentData()
        label = "ω, рад/с" if self._unit == UNIT_RAD_S else "ω, об/с"
        self._plot_widget.setLabel("left", label)
        # Сбросить snap-элементы, чтобы не висели в старых координатах
        self._vline.setVisible(False)
        self._hline.setVisible(False)
        self._snap_dot.setVisible(False)
        self._tooltip.hide()
        # Сброс кеша — единицы изменились, нужен пересчёт
        self._cache_dirty = True
        # Немедленно перерисовать график в новых единицах + авто-центрирование
        self._refresh_plot()
        self._plot_widget.getPlotItem().vb.enableAutoRange()

    def _on_sample(self, t: float, omega: float):
        self._t_buf.append(t)
        self._y_buf.append(omega)
        self._exp_data.append(DataRow(timestamp_s=t, omega_rad_s=omega))
        self._table_widget.notify_new_data()
        self._cache_dirty = True
        if self._mode == MODE_SIMULATION:
            self._sim_panel.update_speed_display(omega)

    def _on_error(self, msg: str):
        self._lbl_current.setText("Ошибка")
        self._on_stop()

    def _on_zoom_axes_changed(self):
        self._zoom_x = self._chk_zoom_x.isChecked()
        self._zoom_y = self._chk_zoom_y.isChecked()
        vb = self._plot_widget.getPlotItem().vb
        # Включаем/выключаем стандартный wheel-zoom pyqtgraph по каждой оси
        vb.setMouseEnabled(x=self._zoom_x, y=self._zoom_y)

    def _apply_line_params(self):
        p = self._line_params
        pen = pg.mkPen(color=p["color"], width=p["width"], style=p["style"])
        sym = p["symbol"]
        if sym:
            self._curve.setData(
                self._curve.xData if self._curve.xData is not None else [],
                self._curve.yData if self._curve.yData is not None else [],
                pen=pen, symbol=sym, symbolSize=p["symbol_size"],
                symbolBrush=pg.mkBrush(p["color"]), symbolPen=pg.mkPen(None),
            )
        else:
            self._curve.setData(
                self._curve.xData if self._curve.xData is not None else [],
                self._curve.yData if self._curve.yData is not None else [],
                pen=pen, symbol=None,
            )
        self._curve.opts["pen"] = pen
        self._curve.opts["symbol"] = sym
        self._curve.opts["symbolSize"] = p["symbol_size"]

    def _on_line_style(self):
        dlg = _LineStyleDialog(self._line_params, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._line_params = dlg.result_params()
            self._apply_line_params()

    def _on_back(self):
        if self._running:
            self._on_stop()
        self.back_requested.emit()

    # =========================================================== chart ======

    def _on_mouse_move(self, evt):
        """Обновляет перекрестие и tooltip при движении мыши."""
        if not self._t_buf:
            return
        pw = self._plot_widget
        pos = evt[0]
        if not pw.sceneBoundingRect().contains(pos):
            self._vline.setVisible(False)
            self._hline.setVisible(False)
            self._snap_dot.setVisible(False)
            self._tooltip.hide()
            return

        mouse_point = pw.getPlotItem().vb.mapSceneToView(pos)
        mx = mouse_point.x()

        # Найти ближайшую точку на кривой — используем кешированные массивы
        if self._t_cache.size == 0:
            return
        ta = self._t_cache
        ya_disp = self._y_cache
        ya_raw = self._y_raw_cache

        idx = int(np.argmin(np.abs(ta - mx)))
        snap_t = ta[idx]
        snap_y = ya_disp[idx]
        snap_omega = ya_raw[idx]

        # Перекрестие
        self._vline.setPos(snap_t)
        self._hline.setPos(snap_y)
        self._vline.setVisible(True)
        self._hline.setVisible(True)

        # Точка
        self._snap_dot.setData([snap_t], [snap_y])
        self._snap_dot.setVisible(True)

        # Значения для tooltip
        rps  = snap_omega / (2.0 * math.pi)
        rpm  = rps * 60.0
        diam = self._exp_data.disk_diameter_mm
        v    = snap_omega * (diam / 2.0)

        unit_str = "рад/с" if self._unit == UNIT_RAD_S else "об/с"
        lines = [
            f"t = {snap_t:.3f} с",
            f"ω = {snap_y:.4f} {unit_str}",
            f"об/с = {rps:.4f}",
            f"RPM = {rpm:.2f}",
            f"V = {v:.2f} мм/с",
        ]
        self._tooltip.update_text(lines)

        # Позиция tooltip: следует за мышью, не вылезает за границы
        scene_rect = pw.sceneBoundingRect()
        sx, sy = pos.x(), pos.y()
        tx = sx + 16
        ty = sy - 10
        tw, th = self._tooltip.width(), self._tooltip.height()
        if tx + tw > scene_rect.right() - 4:
            tx = sx - tw - 16
        if ty + th > scene_rect.bottom() - 4:
            ty = sy - th - 4
        self._tooltip.move(int(tx), int(ty))
        self._tooltip.show()

    def _on_mouse_hover(self, items):
        if not items:
            self._vline.setVisible(False)
            self._hline.setVisible(False)
            self._snap_dot.setVisible(False)
            self._tooltip.hide()

    def _refresh_plot(self):
        if not self._t_buf:
            return

        n = len(self._t_buf)
        # Обновляем кеш только если пришли новые сэмплы или единицы изменились
        if self._cache_dirty or n != self._last_sample_count:
            t_raw = np.array(self._t_buf)
            y_raw = np.array(self._y_buf)
            self._t_cache = t_raw
            self._y_raw_cache = y_raw
            self._y_cache = y_raw / (2.0 * math.pi) if self._unit == UNIT_RPS else y_raw
            self._cache_dirty = False
            self._last_sample_count = n

        t_arr = self._t_cache
        y_arr = self._y_cache

        win = self._spin_window.value()
        t_now = t_arr[-1]
        mask = t_arr >= (t_now - win)
        t_vis = t_arr[mask]
        y_vis = y_arr[mask]

        # Прореживание: не рисовать больше ~800 точек в видимом окне
        _MAX_DRAW = 800
        step = max(1, len(t_vis) // _MAX_DRAW)
        if step > 1:
            t_vis = t_vis[::step]
            y_vis = y_vis[::step]

        self._curve.setData(t_vis, y_vis)

        unit_str = "рад/с" if self._unit == UNIT_RAD_S else "об/с"
        self._lbl_current.setText(f"{y_arr[-1]:.3f} {unit_str}")

        # Масштаб: объединяем в один блокированный вызов чтобы не было двойного repaint
        vb = self._plot_widget.getPlotItem().vb
        vb.blockSignals(True)
        if self._zoom_x:
            x_span = max(win, 5.0)
            vb.setXRange(t_now - x_span, t_now + x_span * 0.02, padding=0)
        if self._zoom_y and len(y_vis) > 0:
            y_min = y_vis.min()
            y_max = y_vis.max()
            y_span = max(y_max - y_min, 1.0)
            margin = y_span * 0.15
            vb.setYRange(max(0.0, y_min - margin), y_max + margin, padding=0)
        vb.blockSignals(False)
        if self._zoom_x or self._zoom_y:
            vb.update()
