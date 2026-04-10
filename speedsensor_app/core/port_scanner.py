"""
Сканер COM-портов с автообнаружением и мониторингом состояния.
Логика автопоиска: пробуем открыть каждый порт и отправить команду 'i',
ждём ответа с маркером 'SpeedSensor' или 'RPS:'.
"""
import time
import threading
from dataclasses import dataclass

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, Signal, QTimer


PROBE_BAUD    = 115200
PROBE_TIMEOUT = 0.5   # сек на ожидание ответа
PROBE_MARKER  = ("speedsensor", "rps:", "pulses:")   # строки в нижнем регистре
SCAN_INTERVAL = 2000  # мс между сканированиями


@dataclass
class PortInfo:
    device: str
    description: str
    vid: int | None
    pid: int | None
    confirmed: bool = False   # True — ответил на probe


class PortScanner(QObject):
    """
    Сканирует доступные COM-порты.
    Эмитирует:
        ports_updated(list[PortInfo])  — список всех портов изменился
        sensor_found(PortInfo)         — найден подтверждённый датчик
        sensor_lost()                  — датчик пропал
    """
    ports_updated = Signal(list)
    sensor_found  = Signal(object)   # PortInfo
    sensor_lost   = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_ports: set[str] = set()
        self._confirmed: PortInfo | None = None
        self._lock = threading.Lock()

        self._timer = QTimer(self)
        self._timer.setInterval(SCAN_INTERVAL)
        self._timer.timeout.connect(self._scan)

    # ----------------------------------------------------------------- API --

    def start(self):
        self._scan()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    @property
    def confirmed_port(self) -> PortInfo | None:
        return self._confirmed

    # ------------------------------------------------------------ internals --

    def _scan(self):
        raw = serial.tools.list_ports.comports()
        infos: list[PortInfo] = [
            PortInfo(
                device=p.device,
                description=p.description or p.device,
                vid=p.vid,
                pid=p.pid,
            )
            for p in sorted(raw, key=lambda x: x.device)
        ]

        current_devices = {i.device for i in infos}

        # Если набор портов изменился — эмитируем
        if current_devices != self._last_ports:
            self._last_ports = current_devices
            self.ports_updated.emit(infos)

        # Проверяем, жив ли ранее подтверждённый датчик
        if self._confirmed and self._confirmed.device not in current_devices:
            self._confirmed = None
            self.sensor_lost.emit()

        # Пробуем подтвердить новые/непроверенные порты в фоне
        unconfirmed = [i for i in infos if not i.confirmed]
        if unconfirmed:
            t = threading.Thread(target=self._probe_ports,
                                 args=(unconfirmed,), daemon=True)
            t.start()

    def _probe_ports(self, ports: list[PortInfo]):
        for info in ports:
            if self._confirmed:
                break
            confirmed = _probe_port(info.device)
            if confirmed:
                info.confirmed = True
                with self._lock:
                    if self._confirmed is None:
                        self._confirmed = info
                        self.sensor_found.emit(info)


def _probe_port(device: str) -> bool:
    """Пытается открыть порт и получить ответ от прошивки."""
    try:
        with serial.Serial(device, PROBE_BAUD, timeout=PROBE_TIMEOUT) as ser:
            ser.reset_input_buffer()
            ser.write(b"i\n")
            deadline = time.monotonic() + PROBE_TIMEOUT
            while time.monotonic() < deadline:
                line = ser.readline().decode("utf-8", errors="ignore").lower()
                if any(m in line for m in PROBE_MARKER):
                    return True
            # Попробуем просто почитать — вдруг уже льёт данные
            ser.write(b"\n")
            line = ser.readline().decode("utf-8", errors="ignore").lower()
            return any(m in line for m in PROBE_MARKER)
    except Exception:
        return False
