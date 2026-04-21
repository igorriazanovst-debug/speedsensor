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
