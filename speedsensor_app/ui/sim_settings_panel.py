"""
Панель настроек симуляции: параметры диска, двигателя, шума датчика.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QSpinBox, QSlider, QLabel, QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal

from core.motor_sim import MotorSimModel


class SimSettingsPanel(QWidget):
    settings_changed = Signal()

    def __init__(self, model: MotorSimModel, parent=None):
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # ── Управление двигателем ────────────────────────────────────────
        grp_motor = QGroupBox("Управление двигателем")
        lay_motor = QVBoxLayout(grp_motor)

        # Слайдер скорости
        spd_row = QHBoxLayout()
        lbl_spd = QLabel("Скорость:")
        spd_row.addWidget(lbl_spd)

        self._slider_rps = QSlider(Qt.Orientation.Horizontal)
        self._slider_rps.setRange(0, 500)   # 0–50.0 рпс × 10
        self._slider_rps.setValue(0)
        self._slider_rps.setTickInterval(50)
        self._slider_rps.setTickPosition(QSlider.TickPosition.TicksBelow)
        spd_row.addWidget(self._slider_rps)

        self._lbl_rps_val = QLabel("0.0 об/с")
        self._lbl_rps_val.setMinimumWidth(80)
        spd_row.addWidget(self._lbl_rps_val)

        lay_motor.addLayout(spd_row)

        # Точная уставка
        form_motor = QFormLayout()
        self._spin_target_rps = QDoubleSpinBox()
        self._spin_target_rps.setRange(0.0, 50.0)
        self._spin_target_rps.setDecimals(2)
        self._spin_target_rps.setSuffix(" об/с")
        self._spin_target_rps.setSingleStep(0.5)
        form_motor.addRow("Уставка:", self._spin_target_rps)

        self._spin_max_rps = QDoubleSpinBox()
        self._spin_max_rps.setRange(1.0, 200.0)
        self._spin_max_rps.setDecimals(1)
        self._spin_max_rps.setSuffix(" об/с")
        self._spin_max_rps.setValue(self._model.max_rps)
        form_motor.addRow("Максимум:", self._spin_max_rps)

        self._spin_inertia = QDoubleSpinBox()
        self._spin_inertia.setRange(0.1, 10.0)
        self._spin_inertia.setDecimals(2)
        self._spin_inertia.setSingleStep(0.1)
        self._spin_inertia.setValue(self._model.inertia_scale)
        form_motor.addRow("Инерция (×):", self._spin_inertia)

        self._spin_torque = QDoubleSpinBox()
        self._spin_torque.setRange(0.1, 20.0)
        self._spin_torque.setDecimals(2)
        self._spin_torque.setSingleStep(0.1)
        self._spin_torque.setValue(self._model.torque_k)
        form_motor.addRow("Момент привода:", self._spin_torque)

        self._spin_friction = QDoubleSpinBox()
        self._spin_friction.setRange(0.01, 5.0)
        self._spin_friction.setDecimals(3)
        self._spin_friction.setSingleStep(0.05)
        self._spin_friction.setValue(self._model.friction_k)
        form_motor.addRow("Трение:", self._spin_friction)

        lay_motor.addLayout(form_motor)
        root.addWidget(grp_motor)

        # ── Параметры диска ──────────────────────────────────────────────
        grp_disk = QGroupBox("Параметры диска")
        form_disk = QFormLayout(grp_disk)

        self._spin_diameter = QDoubleSpinBox()
        self._spin_diameter.setRange(10.0, 500.0)
        self._spin_diameter.setDecimals(1)
        self._spin_diameter.setSuffix(" мм")
        self._spin_diameter.setValue(self._model.disk_diameter_mm)
        form_disk.addRow("Диаметр:", self._spin_diameter)

        self._spin_mass = QDoubleSpinBox()
        self._spin_mass.setRange(1.0, 2000.0)
        self._spin_mass.setDecimals(1)
        self._spin_mass.setSuffix(" г")
        self._spin_mass.setValue(self._model.disk_mass_g)
        form_disk.addRow("Масса:", self._spin_mass)

        self._spin_slots = QSpinBox()
        self._spin_slots.setRange(1, 360)
        self._spin_slots.setValue(self._model.slots)
        form_disk.addRow("Прорезей:", self._spin_slots)

        root.addWidget(grp_disk)

        # ── Параметры датчика ────────────────────────────────────────────
        grp_noise = QGroupBox("Параметры датчика / шум")
        form_noise = QFormLayout(grp_noise)

        self._spin_noise = QDoubleSpinBox()
        self._spin_noise.setRange(0.0, 20.0)
        self._spin_noise.setDecimals(2)
        self._spin_noise.setSuffix(" %")
        self._spin_noise.setValue(self._model.noise_percent)
        form_noise.addRow("Уровень шума:", self._spin_noise)

        self._spin_jitter = QDoubleSpinBox()
        self._spin_jitter.setRange(0.0, 50.0)
        self._spin_jitter.setDecimals(1)
        self._spin_jitter.setSuffix(" мс")
        self._spin_jitter.setValue(self._model.sensor_jitter_ms)
        form_noise.addRow("Джиттер:", self._spin_jitter)

        root.addWidget(grp_noise)

        # ── Кнопка стоп ─────────────────────────────────────────────────
        self._btn_stop = QPushButton("⏹  Стоп (ω → 0)")
        self._btn_stop.clicked.connect(self._on_stop)
        root.addWidget(self._btn_stop)

        root.addStretch()

        # ── Связи ────────────────────────────────────────────────────────
        self._slider_rps.valueChanged.connect(self._on_slider)
        self._spin_target_rps.valueChanged.connect(self._on_spin_rps)
        self._spin_max_rps.valueChanged.connect(self._apply)
        self._spin_inertia.valueChanged.connect(self._apply)
        self._spin_torque.valueChanged.connect(self._apply)
        self._spin_friction.valueChanged.connect(self._apply)
        self._spin_diameter.valueChanged.connect(self._apply)
        self._spin_mass.valueChanged.connect(self._apply)
        self._spin_slots.valueChanged.connect(self._apply)
        self._spin_noise.valueChanged.connect(self._apply)
        self._spin_jitter.valueChanged.connect(self._apply)

    # --------------------------------------------------------------- slots --

    def _on_slider(self, val: int):
        rps = val / 10.0
        self._spin_target_rps.blockSignals(True)
        self._spin_target_rps.setValue(rps)
        self._spin_target_rps.blockSignals(False)
        self._lbl_rps_val.setText(f"{rps:.1f} об/с")
        self._apply()

    def _on_spin_rps(self, val: float):
        self._slider_rps.blockSignals(True)
        self._slider_rps.setValue(int(val * 10))
        self._slider_rps.blockSignals(False)
        self._lbl_rps_val.setText(f"{val:.1f} об/с")
        self._apply()

    def _on_stop(self):
        self._spin_target_rps.setValue(0.0)

    def _apply(self):
        m = self._model
        m.target_rps = self._spin_target_rps.value()
        m.max_rps = self._spin_max_rps.value()
        m.inertia_scale = self._spin_inertia.value()
        m.torque_k = self._spin_torque.value()
        m.friction_k = self._spin_friction.value()
        m.disk_diameter_mm = self._spin_diameter.value()
        m.disk_mass_g = self._spin_mass.value()
        m.slots = self._spin_slots.value()
        m.noise_percent = self._spin_noise.value()
        m.sensor_jitter_ms = self._spin_jitter.value()

        # Обновить максимум слайдера
        max_val = int(m.max_rps * 10)
        self._slider_rps.setMaximum(max_val)

        self.settings_changed.emit()
