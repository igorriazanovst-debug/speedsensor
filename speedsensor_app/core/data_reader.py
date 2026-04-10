"""
Поток чтения данных — реальный Serial или симуляция.
Эмитирует сигнал new_sample(timestamp_s: float, omega_rad_s: float).
"""
import time
import math
import re

from PySide6.QtCore import QThread, Signal

from core.motor_sim import MotorSimModel


class DataReaderThread(QThread):
    new_sample = Signal(float, float)   # (timestamp_s, omega_rad_s)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._sim_mode = True
        self._sim: MotorSimModel | None = None

        # Serial params
        self._port: str = ""
        self._baud: int = 115200
        self._sample_rate_hz: int = 20

    # ---------------------------------------------------------------- setup --

    def configure_sim(self, model: MotorSimModel, sample_rate_hz: int = 20):
        self._sim_mode = True
        self._sim = model
        self._sample_rate_hz = sample_rate_hz

    def configure_serial(self, port: str, baud: int, sample_rate_hz: int = 20):
        self._sim_mode = False
        self._port = port
        self._baud = baud
        self._sample_rate_hz = sample_rate_hz

    # ----------------------------------------------------------------- run --

    def run(self):
        self._running = True
        if self._sim_mode:
            self._run_sim()
        else:
            self._run_serial()

    def stop(self):
        self._running = False
        self.wait(2000)

    # ------------------------------------------------------------ sim loop --

    def _run_sim(self):
        if self._sim is None:
            self._sim = MotorSimModel()
        self._sim.reset()
        interval = 1.0 / max(self._sample_rate_hz, 1)
        t0 = time.monotonic()
        while self._running:
            t_start = time.monotonic()
            omega = self._sim.step()
            self.new_sample.emit(t_start - t0, omega)
            elapsed = time.monotonic() - t_start
            sleep = interval - elapsed
            if sleep > 0:
                time.sleep(sleep)

    # --------------------------------------------------------- serial loop --

    def _run_serial(self):
        try:
            import serial
        except ImportError:
            self.error.emit("pyserial не установлен")
            return

        try:
            ser = serial.Serial(self._port, self._baud, timeout=1.0)
        except Exception as e:
            self.error.emit(f"Ошибка открытия порта {self._port}: {e}")
            return

        t0 = time.monotonic()
        # Формат прошивки: "Pulses: N | RPS: X.XXX | RPM: X.X | V: X.X mm/s | Pin: HIGH/LOW"
        pattern = re.compile(r"RPS:\s*([\d.]+)")

        try:
            while self._running:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                m = pattern.search(line)
                if m:
                    rps = float(m.group(1))
                    omega = rps * 2.0 * math.pi
                    self.new_sample.emit(time.monotonic() - t0, omega)
        except Exception as e:
            self.error.emit(f"Ошибка чтения порта: {e}")
        finally:
            ser.close()
