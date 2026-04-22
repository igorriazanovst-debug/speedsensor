"""
Дополнительный патч — исправляет то, что patch_home_tab.py не нашёл:
  1. core/port_scanner.py  — тело _probe_port (реальная версия из файла)
  2. ui/sensor_connect_widget.py — ручной probe через _probe_port теперь возвращает PortInfo|None

Запуск из папки speedsensor_app:
    python patch_home_tab_fix.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(BASE, "speedsensor_app")):
    BASE = os.path.join(BASE, "speedsensor_app")
print(f"[fix] Корень проекта: {BASE}")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  OK  {os.path.relpath(path, BASE)}")

def patch_once(path, old, new, label=""):
    text = read(path)
    if old not in text:
        print(f"  --  {os.path.relpath(path, BASE)}: маркер не найден ({label})")
        return False
    if new in text:
        print(f"  ~~  {os.path.relpath(path, BASE)}: уже применён ({label})")
        return False
    write(path, text.replace(old, new, 1))
    return True


# ══════════════════════════════════════════════════════════════════════════════
# 1. core/port_scanner.py — тело _probe_port (реальная версия)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1] core/port_scanner.py — тело _probe_port")

SCANNER_PATH = os.path.join(BASE, "core", "port_scanner.py")

OLD_PROBE_BODY = '''\
    try:
        with serial.Serial(device, PROBE_BAUD, timeout=PROBE_TIMEOUT) as ser:
            ser.reset_input_buffer()
            ser.write(b"i\\n")
            deadline = time.monotonic() + PROBE_TIMEOUT
            while time.monotonic() < deadline:
                line = ser.readline().decode("utf-8", errors="ignore").lower()
                if any(m in line for m in PROBE_MARKER):
                    return True
            # Попробуем просто почитать — вдруг уже льёт данные
            ser.write(b"\\n")
            line = ser.readline().decode("utf-8", errors="ignore").lower()
            return any(m in line for m in PROBE_MARKER)
    except Exception:
        return False'''

NEW_PROBE_BODY = '''\
    try:
        with serial.Serial(device, PROBE_BAUD, timeout=PROBE_TIMEOUT) as ser:
            ser.reset_input_buffer()
            ser.write(b"i\\n")
            deadline = time.monotonic() + PROBE_TIMEOUT
            buf = ""
            while time.monotonic() < deadline:
                chunk = ser.read(ser.in_waiting or 1).decode("utf-8", errors="ignore")
                buf += chunk
                if any(m in buf.lower() for m in PROBE_MARKER):
                    break
            else:
                # Попробуем ещё раз — вдруг уже льёт данные
                ser.write(b"\\n")
                line = ser.readline().decode("utf-8", errors="ignore")
                buf += line
                if not any(m in buf.lower() for m in PROBE_MARKER):
                    return None
            # Парсим идентификационные поля
            name = ""
            purpose = ""
            scenarios = ""
            for line in buf.splitlines():
                ls = line.strip()
                if ls.lower().startswith("name:"):
                    name = ls[5:].strip()
                elif ls.lower().startswith("purpose:"):
                    purpose = ls[8:].strip()
                elif ls.lower().startswith("scenarios:"):
                    scenarios = ls[10:].strip()
            return PortInfo(
                device=device,
                description="",
                vid=None,
                pid=None,
                confirmed=True,
                sensor_name=name,
                sensor_purpose=purpose,
                sensor_scenarios=scenarios,
            )
    except Exception:
        return None'''

patch_once(SCANNER_PATH, OLD_PROBE_BODY, NEW_PROBE_BODY, "_probe_port body")


# ══════════════════════════════════════════════════════════════════════════════
# 2. ui/sensor_connect_widget.py — ручной probe: обрабатываем PortInfo | None
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2] ui/sensor_connect_widget.py — ручной probe")

SCW_PATH = os.path.join(BASE, "ui", "sensor_connect_widget.py")

OLD_DO_PROBE = '''\
        def do_probe():
            ok = _probe_port(port)
            # Вернуться в UI-поток
            if ok:
                from PySide6.QtCore import QMetaObject, Q_ARG
                info = PortInfo(device=port, description="ручное подключение",
                                vid=None, pid=None, confirmed=True)
                self._confirmed_port = info
                self._on_sensor_found(info)
            else:
                self._set_state_error(
                    f"Порт {port} не отвечает.\\n"
                    "Проверьте прошивку и скорость соединения."
                )
            self._btn_connect.setEnabled(True)'''

NEW_DO_PROBE = '''\
        def do_probe():
            result = _probe_port(port)
            if result is not None:
                self._confirmed_port = result
                self._on_sensor_found(result)
            else:
                self._set_state_error(
                    f"Порт {port} не отвечает.\\n"
                    "Проверьте прошивку и скорость соединения."
                )
            self._btn_connect.setEnabled(True)'''

patch_once(SCW_PATH, OLD_DO_PROBE, NEW_DO_PROBE, "do_probe body")


# ══════════════════════════════════════════════════════════════════════════════
# 3. ui/main_window.py — shared scanner передаём в SensorConnectWidget
#    SensorConnectWidget.__init__ создаёт свой scanner — нужно его заменить
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3] ui/sensor_connect_widget.py — принимать внешний scanner")

# SensorConnectWidget.__init__ сейчас: self._scanner = PortScanner(self)
# Меняем на: принимаем scanner как параметр (с дефолтом None → создаём свой)

OLD_SCW_INIT = '''\
    def __init__(self, parent=None):
        super().__init__(parent)
        self._confirmed_port: PortInfo | None = None

        self._scanner = PortScanner(self)
        self._scanner.ports_updated.connect(self._on_ports_updated)
        self._scanner.sensor_found.connect(self._on_sensor_found)
        self._scanner.sensor_lost.connect(self._on_sensor_lost)

        self._build_ui()
        self._set_state_searching()
        self._scanner.start()'''

NEW_SCW_INIT = '''\
    def __init__(self, scanner: "PortScanner | None" = None, parent=None):
        super().__init__(parent)
        self._confirmed_port: PortInfo | None = None

        self._scanner = scanner if scanner is not None else PortScanner(self)
        self._scanner.ports_updated.connect(self._on_ports_updated)
        self._scanner.sensor_found.connect(self._on_sensor_found)
        self._scanner.sensor_lost.connect(self._on_sensor_lost)

        self._build_ui()
        self._set_state_searching()
        # Если scanner внешний — он уже запущен; не запускаем повторно
        if scanner is None:
            self._scanner.start()'''

patch_once(SCW_PATH, OLD_SCW_INIT, NEW_SCW_INIT, "SensorConnectWidget __init__")

# ══════════════════════════════════════════════════════════════════════════════
# 4. ui/main_window.py — передать shared_scanner в SensorConnectWidget
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4] ui/main_window.py — передать shared_scanner в SensorConnectWidget")

MW_PATH = os.path.join(BASE, "ui", "main_window.py")

OLD_SCW_CREATE = "        self._sensor_connect = SensorConnectWidget()"
NEW_SCW_CREATE = "        self._sensor_connect = SensorConnectWidget(scanner=self._shared_scanner)"

patch_once(MW_PATH, OLD_SCW_CREATE, NEW_SCW_CREATE, "SensorConnectWidget creation")

print("\n[fix] Готово.")
