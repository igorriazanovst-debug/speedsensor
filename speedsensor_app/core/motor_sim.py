"""
Физическая модель двигателя с диском для режима «Моделирование эксперимента».
Симулирует разгон/торможение с инерцией, шумом датчика и джиттером.
"""
import math
import random
import time


class MotorSimModel:
    """
    Простая модель ротора с инерцией.

    Уравнение движения:
        J * dω/dt = τ_drive - τ_friction

    где:
        J           — момент инерции [кг·м²]
        τ_drive     — момент движущей силы (пропорционален уставке)
        τ_friction  — момент трения (пропорционален ω)
    """

    def __init__(self):
        # Параметры диска
        self.disk_diameter_mm: float = 75.0   # мм
        self.disk_mass_g: float = 50.0        # г
        self.slots: int = 20                  # прорезей

        # Параметры двигателя
        self.target_rps: float = 0.0          # уставка об/с
        self.max_rps: float = 50.0            # максимум об/с
        self.torque_k: float = 2.0            # коэф. момента привода
        self.friction_k: float = 0.3          # коэф. трения
        self.inertia_scale: float = 1.0       # масштаб инерции (0.1–5.0)

        # Параметры шума датчика
        self.noise_percent: float = 1.0       # % от текущего значения
        self.sensor_jitter_ms: float = 2.0    # джиттер измерения, мс

        # Внутреннее состояние
        self._omega: float = 0.0              # рад/с
        self._last_time: float = time.monotonic()

    # ---------------------------------------------------------------- props --

    @property
    def disk_radius_m(self) -> float:
        return (self.disk_diameter_mm / 2.0) / 1000.0

    @property
    def inertia(self) -> float:
        """Момент инерции тонкого диска: J = 0.5 * m * r²"""
        m = (self.disk_mass_g / 1000.0) * self.inertia_scale
        return 0.5 * m * self.disk_radius_m ** 2

    @property
    def omega(self) -> float:
        return self._omega

    @property
    def rps(self) -> float:
        return self._omega / (2.0 * math.pi)

    @property
    def rpm(self) -> float:
        return self.rps * 60.0

    @property
    def rad_s(self) -> float:
        return self._omega

    # ---------------------------------------------------------------- step --

    def step(self) -> float:
        """Шаг симуляции. Возвращает текущую угловую скорость (рад/с) с шумом."""
        now = time.monotonic()
        dt = now - self._last_time
        self._last_time = now

        dt = max(min(dt, 0.2), 1e-4)

        target_omega = self.target_rps * 2.0 * math.pi
        tau_drive = self.torque_k * (target_omega - self._omega)
        tau_friction = self.friction_k * self._omega

        J = max(self.inertia, 1e-9)
        domega = (tau_drive - tau_friction) / J * dt
        self._omega = max(0.0, self._omega + domega)

        # Ограничение максимума
        max_omega = self.max_rps * 2.0 * math.pi
        self._omega = min(self._omega, max_omega)

        # Шум
        noise = self._omega * (self.noise_percent / 100.0) * random.gauss(0, 1)
        measured = max(0.0, self._omega + noise)

        return measured

    def reset(self):
        self._omega = 0.0
        self._last_time = time.monotonic()
