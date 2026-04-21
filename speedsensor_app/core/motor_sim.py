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
        # Параметры диска/датчика (заполняются из сценария)
        self.disk_diameter_mm: float = 75.0
        self.slots: int = 20

        # Реостат: 0–100 %
        self.rheostat_pct: float = 0.0

        # Диапазон скоростей установки
        self.max_rps: float = 10.0          # об/с при реостате 100%

        # Шум датчика
        self.noise_percent: float = 1.0     # % от текущего значения

    # ---------------------------------------------------------------- props --

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
