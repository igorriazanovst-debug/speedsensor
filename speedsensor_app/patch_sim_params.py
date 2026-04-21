#!/usr/bin/env python3
"""
Патч SpeedSensor Lab:
  1. motor_sim.py      — добавляет max_rpm (конвертируется в max_rps),
                         disk_diameter_mm, slots, slot_width_mm, slot_gap_mm
  2. sim_settings_panel.py — добавляет группы «Параметры двигателя»
                              и «Диск датчика» с полями ввода
Запуск: python patch_sim_params.py <путь к speedsensor_app>
"""
import sys
import os
import re

# ─────────────────────────────────────────────────────────────── helpers ──

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  ✓ {path}")


# ═══════════════════════════════════════════════════════ motor_sim.py ══════

MOTOR_SIM_NEW = '''\
"""
Модель установки: двигатель постоянного тока с реостатом.

Реостат (0–100%) линейно задаёт угловую скорость в диапазоне [0, max_rps].
Скорость изменяется мгновенно (без инерции) — соответствует реальной установке,
где реостат плавно регулирует напряжение на двигателе.

Датчик добавляет гауссовский шум (noise_percent % от текущего значения).
"""
import math
import random


class MotorSimModel:
    def __init__(self):
        # ── Параметры двигателя ──────────────────────────────────────────
        self.max_rpm: float = 600.0         # макс. обороты в минуту при реостате 100%

        # ── Параметры диска датчика ──────────────────────────────────────
        self.disk_diameter_mm: float = 75.0  # диаметр диска, мм
        self.slots: int = 20                 # количество пропилов
        self.slot_width_mm: float = 5.0      # ширина пропила, мм
        self.slot_gap_mm: float = 6.0        # ширина перемычки, мм

        # ── Реостат: 0–100 % ─────────────────────────────────────────────
        self.rheostat_pct: float = 0.0

        # ── Шум датчика ──────────────────────────────────────────────────
        self.noise_percent: float = 1.0      # % от текущего значения

    # ---------------------------------------------------------------- derived props --

    @property
    def max_rps(self) -> float:
        """Максимальная скорость в об/с."""
        return self.max_rpm / 60.0

    @property
    def disk_circumference_mm(self) -> float:
        return math.pi * self.disk_diameter_mm

    @property
    def slot_period_mm(self) -> float:
        """Период решётки (пропил + перемычка), мм."""
        return self.slot_width_mm + self.slot_gap_mm

    @property
    def target_rps(self) -> float:
        """Текущая целевая скорость (об/с) по положению реостата."""
        return self.max_rps * self.rheostat_pct / 100.0

    @property
    def target_omega(self) -> float:
        """Текущая целевая угловая скорость (рад/с)."""
        return self.target_rps * 2.0 * math.pi

    # ---------------------------------------------------------------- step --

    def step(self) -> float:
        """Возвращает текущую угловую скорость (рад/с) с шумом датчика."""
        omega = self.target_omega
        if omega > 0 and self.noise_percent > 0:
            noise = omega * (self.noise_percent / 100.0) * random.gauss(0, 1)
            omega = max(0.0, omega + noise)
        return omega

    def reset(self):
        pass  # состояния нет — сброс не нужен
'''


# ═══════════════════════════════════════════════════════ sim_settings_panel.py ══

SIM_PANEL_NEW = '''\
"""
Панель управления симуляцией: реостат + параметры двигателя + диск датчика.
"""
import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.motor_sim import MotorSimModel

C_ACCENT = "#a6e3a1"
C_TEXT   = "#cdd6f4"
C_BG2    = "#181825"
C_MUTED  = "#6c7086"
C_WARN   = "#f38ba8"


class SimSettingsPanel(QWidget):
    settings_changed = Signal()

    def __init__(self, model: MotorSimModel, parent=None):
        super().__init__(parent)
        self._model = model
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(14)
        scroll.setWidget(container)

        # ── Заголовок ────────────────────────────────────────────────────
        lbl_title = QLabel("Управление симуляцией")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {C_TEXT};")
        root.addWidget(lbl_title)

        # ── Слайдер реостата ─────────────────────────────────────────────
        grp = QGroupBox("Положение реостата")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)

        self._lbl_pct = QLabel("0 %")
        self._lbl_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_pct.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._lbl_pct.setStyleSheet(f"color: {C_ACCENT};")
        lay.addWidget(self._lbl_pct)

        self._slider = QSlider(Qt.Orientation.Vertical)
        self._slider.setRange(0, 100)
        self._slider.setMinimumHeight(120)
        self._slider.setStyleSheet("")
        lay.addWidget(self._slider, alignment=Qt.AlignmentFlag.AlignHCenter)

        row = QHBoxLayout()
        row.addStretch()
        self._btn_stop = QPushButton("⏹  Стоп")
        self._btn_stop.clicked.connect(self._on_stop)
        row.addWidget(self._btn_stop)
        row.addStretch()
        lay.addLayout(row)

        root.addWidget(grp)

        # ── Текущая скорость ──────────────────────────────────────────────
        grp_spd = QGroupBox("Текущая скорость")
        spd_lay = QVBoxLayout(grp_spd)

        self._lbl_rps = QLabel("0.00 об/с")
        self._lbl_rps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_rps.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._lbl_rps.setStyleSheet(f"color: {C_ACCENT};")
        spd_lay.addWidget(self._lbl_rps)

        self._lbl_rpm = QLabel("0.0 RPM")
        self._lbl_rpm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_rpm.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        spd_lay.addWidget(self._lbl_rpm)

        root.addWidget(grp_spd)

        # ── Параметры двигателя ───────────────────────────────────────────
        grp_motor = QGroupBox("Параметры двигателя")
        fm = QFormLayout(grp_motor)
        fm.setSpacing(6)

        self._spin_max_rpm = QDoubleSpinBox()
        self._spin_max_rpm.setRange(10.0, 100_000.0)
        self._spin_max_rpm.setDecimals(0)
        self._spin_max_rpm.setSingleStep(50.0)
        self._spin_max_rpm.setSuffix(" RPM")
        self._spin_max_rpm.setValue(self._model.max_rpm)
        self._spin_max_rpm.setToolTip(
            "Максимальные обороты двигателя при реостате 100%"
        )
        self._spin_max_rpm.valueChanged.connect(self._on_motor_changed)
        fm.addRow("Макс. обороты:", self._spin_max_rpm)

        self._lbl_max_rps = QLabel(f"= {self._model.max_rps:.2f} об/с")
        self._lbl_max_rps.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        fm.addRow("", self._lbl_max_rps)

        root.addWidget(grp_motor)

        # ── Параметры диска датчика ───────────────────────────────────────
        grp_disk = QGroupBox("Диск датчика угловой скорости")
        fd = QFormLayout(grp_disk)
        fd.setSpacing(6)

        self._spin_diameter = QDoubleSpinBox()
        self._spin_diameter.setRange(10.0, 500.0)
        self._spin_diameter.setDecimals(1)
        self._spin_diameter.setSingleStep(1.0)
        self._spin_diameter.setSuffix(" мм")
        self._spin_diameter.setValue(self._model.disk_diameter_mm)
        self._spin_diameter.setToolTip("Внешний диаметр диска")
        self._spin_diameter.valueChanged.connect(self._on_disk_changed)
        fd.addRow("Диаметр:", self._spin_diameter)

        self._spin_slots = QSpinBox()
        self._spin_slots.setRange(1, 1000)
        self._spin_slots.setValue(self._model.slots)
        self._spin_slots.setToolTip("Количество пропилов (прорезей)")
        self._spin_slots.valueChanged.connect(self._on_disk_changed)
        fd.addRow("Кол-во пропилов:", self._spin_slots)

        self._spin_slot_width = QDoubleSpinBox()
        self._spin_slot_width.setRange(0.1, 100.0)
        self._spin_slot_width.setDecimals(1)
        self._spin_slot_width.setSingleStep(0.5)
        self._spin_slot_width.setSuffix(" мм")
        self._spin_slot_width.setValue(self._model.slot_width_mm)
        self._spin_slot_width.setToolTip("Ширина пропила")
        self._spin_slot_width.valueChanged.connect(self._on_disk_changed)
        fd.addRow("Ширина пропила:", self._spin_slot_width)

        self._spin_slot_gap = QDoubleSpinBox()
        self._spin_slot_gap.setRange(0.1, 100.0)
        self._spin_slot_gap.setDecimals(1)
        self._spin_slot_gap.setSingleStep(0.5)
        self._spin_slot_gap.setSuffix(" мм")
        self._spin_slot_gap.setValue(self._model.slot_gap_mm)
        self._spin_slot_gap.setToolTip("Ширина перемычки между пропилами")
        self._spin_slot_gap.valueChanged.connect(self._on_disk_changed)
        fd.addRow("Ширина перемычки:", self._spin_slot_gap)

        # Производные (только чтение)
        self._lbl_period = QLabel()
        self._lbl_period.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        fd.addRow("Период решётки:", self._lbl_period)

        self._lbl_circumf = QLabel()
        self._lbl_circumf.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        fd.addRow("Длина окружности:", self._lbl_circumf)

        self._lbl_disk_warn = QLabel("")
        self._lbl_disk_warn.setStyleSheet(f"color: {C_WARN}; font-size: 11px;")
        self._lbl_disk_warn.setWordWrap(True)
        fd.addRow(self._lbl_disk_warn)

        root.addWidget(grp_disk)
        root.addStretch()

        # ── Связи ────────────────────────────────────────────────────────
        self._slider.valueChanged.connect(self._on_slider)
        self._update_disk_info()

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

    def _on_motor_changed(self):
        self._model.max_rpm = self._spin_max_rpm.value()
        self._lbl_max_rps.setText(f"= {self._model.max_rps:.2f} об/с")
        # Обновить отображение текущей скорости
        rps = self._model.target_rps
        self._lbl_rps.setText(f"{rps:.2f} об/с")
        self._lbl_rpm.setText(f"{rps * 60:.1f} RPM")
        self.settings_changed.emit()

    def _on_disk_changed(self):
        self._model.disk_diameter_mm = self._spin_diameter.value()
        self._model.slots = self._spin_slots.value()
        self._model.slot_width_mm = self._spin_slot_width.value()
        self._model.slot_gap_mm = self._spin_slot_gap.value()
        self._update_disk_info()
        self.settings_changed.emit()

    def _update_disk_info(self):
        period = self._model.slot_period_mm
        circumf = self._model.disk_circumference_mm
        self._lbl_period.setText(f"{period:.1f} мм")
        self._lbl_circumf.setText(f"{circumf:.1f} мм")

        # Предупреждение: пропилы не вмещаются на диск
        total_slots_mm = self._model.slots * period
        warn = ""
        if total_slots_mm > circumf * 0.999:
            warn = (
                f"⚠ Пропилы не вмещаются: "
                f"{total_slots_mm:.1f} мм > {circumf:.1f} мм"
            )
        self._lbl_disk_warn.setText(warn)

    def update_speed_display(self, omega_rad_s: float):
        """Вызывается из ExperimentWidget при каждом новом сэмпле."""
        rps = omega_rad_s / (2 * math.pi)
        self._lbl_rps.setText(f"{rps:.2f} об/с")
        self._lbl_rpm.setText(f"{rps * 60:.1f} RPM")
'''


# ═══════════════════════════════════════════════════════════════ main ══

def main():
    if len(sys.argv) < 2:
        print("Использование: python patch_sim_params.py <путь_к_speedsensor_app>")
        sys.exit(1)

    base = sys.argv[1].rstrip("/\\")
    if not os.path.isdir(base):
        print(f"Директория не найдена: {base}")
        sys.exit(1)

    motor_sim_path  = os.path.join(base, "core", "motor_sim.py")
    sim_panel_path  = os.path.join(base, "ui", "sim_settings_panel.py")

    for p in [motor_sim_path, sim_panel_path]:
        if not os.path.exists(p):
            print(f"Файл не найден: {p}")
            sys.exit(1)

    print("Применяем патч…")
    write(motor_sim_path, MOTOR_SIM_NEW)
    write(sim_panel_path, SIM_PANEL_NEW)
    print("Готово.")


if __name__ == "__main__":
    main()
