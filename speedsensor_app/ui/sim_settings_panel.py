"""
Панель управления симуляцией: реостат + текущая скорость.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.motor_sim import MotorSimModel

C_ACCENT = "#a6e3a1"
C_TEXT   = "#cdd6f4"
C_BG2    = "#181825"


class SimSettingsPanel(QWidget):
    settings_changed = Signal()

    def __init__(self, model: MotorSimModel, parent=None):
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(14)

        # ── Заголовок ────────────────────────────────────────────────────
        lbl_title = QLabel("Реостат")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {C_TEXT};")
        root.addWidget(lbl_title)

        # ── Слайдер реостата ─────────────────────────────────────────────
        grp = QGroupBox("Положение реостата")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)

        # Метка процента
        self._lbl_pct = QLabel("0 %")
        self._lbl_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_pct.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._lbl_pct.setStyleSheet(f"color: {C_ACCENT};")
        lay.addWidget(self._lbl_pct)

        # Вертикальный слайдер (как реостат)
        self._slider = QSlider(Qt.Orientation.Vertical)
        self._slider.setRange(0, 100)
        self._slider.setValue(0)
        self._slider.setTickInterval(10)
        self._slider.setTickPosition(QSlider.TickPosition.TicksRight)
        self._slider.setMinimumHeight(180)
        self._slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: #313244;
                width: 8px;
                border-radius: 4px;
            }
            QSlider::handle:vertical {
                background: #cba6f7;
                height: 20px;
                width: 20px;
                margin: 0 -6px;
                border-radius: 10px;
            }
            QSlider::sub-page:vertical {
                background: #a6e3a1;
                border-radius: 4px;
            }
        """)

        # Метки шкалы
        scale_lay = QHBoxLayout()
        slider_wrap = QHBoxLayout()

        lbl_scale = QVBoxLayout()
        for v in [100, 75, 50, 25, 0]:
            lbl = QLabel(f"{v}")
            lbl.setStyleSheet("color: #6c7086; font-size: 10px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_scale.addWidget(lbl)

        slider_wrap.addStretch()
        slider_wrap.addWidget(self._slider)
        slider_wrap.addLayout(lbl_scale)
        slider_wrap.addStretch()
        lay.addLayout(slider_wrap)

        root.addWidget(grp)

        # ── Текущая скорость ─────────────────────────────────────────────
        grp_spd = QGroupBox("Текущая скорость")
        spd_lay = QVBoxLayout(grp_spd)

        self._lbl_rps = QLabel("0.00 об/с")
        self._lbl_rps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_rps.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._lbl_rps.setStyleSheet(f"color: {C_ACCENT};")
        spd_lay.addWidget(self._lbl_rps)

        self._lbl_rpm = QLabel("0.0 RPM")
        self._lbl_rpm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_rpm.setStyleSheet(f"color: #6c7086; font-size: 11px;")
        spd_lay.addWidget(self._lbl_rpm)

        root.addWidget(grp_spd)

        # ── Кнопка стоп ──────────────────────────────────────────────────
        self._btn_stop = QPushButton("⏹  Стоп")
        self._btn_stop.clicked.connect(self._on_stop)
        root.addWidget(self._btn_stop)

        root.addStretch()

        # ── Связи ────────────────────────────────────────────────────────
        self._slider.valueChanged.connect(self._on_slider)

    # --------------------------------------------------------------- slots --

    def _on_slider(self, val: int):
        self._model.rheostat_pct = float(val)
        self._lbl_pct.setText(f"{val} %")
        rps = self._model.target_rps
        self._lbl_rps.setText(f"{rps:.2f} об/с")
        self._lbl_rpm.setText(f"{rps * 60:.1f} RPM")
        self.settings_changed.emit()

    def _on_stop(self):
        self._slider.setValue(0)

    def update_speed_display(self, omega_rad_s: float):
        """Вызывается из ExperimentWidget при каждом новом сэмпле."""
        rps = omega_rad_s / (2 * 3.141592653589793)
        self._lbl_rps.setText(f"{rps:.2f} об/с")
        self._lbl_rpm.setText(f"{rps * 60:.1f} RPM")
