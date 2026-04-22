"""
Патч: исправляет экран подключения датчика после введения shared PortScanner.

Проблемы:
  1. _on_back и _on_start вызывают self._scanner.stop() — останавливают shared scanner,
     HomeWidget перестаёт получать обновления
  2. _on_mode_selected в main_window перезапускает scanner через self._sensor_connect._scanner.start()
     но shared scanner уже запущен → дублирование сканирований
  3. При повторном входе на экран подключения список портов пустой, т.к.
     ports_updated не эмитируется повторно

Исправления:
  A. sensor_connect_widget.py: stop/start scanner только если он не shared
     (добавляем self._scanner_is_shared)
  B. sensor_connect_widget.py: при показе экрана — синхронизировать состояние
     из уже найденного confirmed_port (метод sync_state)
  C. main_window.py: _on_mode_selected вызывает sync_state вместо start()

Запуск из папки speedsensor_app:
    python patch_sensor_connect_fix.py
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
        print(f"  --  {os.path.relpath(path, BASE)}: не найден ({label})")
        return False
    if new in text:
        print(f"  ~~  {os.path.relpath(path, BASE)}: уже применён ({label})")
        return False
    write(path, text.replace(old, new, 1))
    return True


SCW_PATH = os.path.join(BASE, "ui", "sensor_connect_widget.py")
MW_PATH  = os.path.join(BASE, "ui", "main_window.py")

# ─────────────────────────────────────────────────────────────────────────────
# A. SensorConnectWidget.__init__: пометить scanner как shared, не запускать
# ─────────────────────────────────────────────────────────────────────────────
print("\n[A] sensor_connect_widget.py — пометка shared scanner")

# Патч для версии ПОСЛЕ patch_home_tab_fix.py (с параметром scanner=None)
OLD_INIT_PATCHED = '''\
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

NEW_INIT_PATCHED = '''\
    def __init__(self, scanner: "PortScanner | None" = None, parent=None):
        super().__init__(parent)
        self._confirmed_port: PortInfo | None = None
        self._scanner_is_shared = scanner is not None

        self._scanner = scanner if scanner is not None else PortScanner(self)
        self._scanner.ports_updated.connect(self._on_ports_updated)
        self._scanner.sensor_found.connect(self._on_sensor_found)
        self._scanner.sensor_lost.connect(self._on_sensor_lost)

        self._build_ui()
        self._set_state_searching()
        if not self._scanner_is_shared:
            self._scanner.start()'''

# Также патч для оригинальной версии (без параметра scanner) — на случай если fix не применялся
OLD_INIT_ORIG = '''\
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

NEW_INIT_ORIG = '''\
    def __init__(self, scanner: "PortScanner | None" = None, parent=None):
        super().__init__(parent)
        self._confirmed_port: PortInfo | None = None
        self._scanner_is_shared = scanner is not None

        self._scanner = scanner if scanner is not None else PortScanner(self)
        self._scanner.ports_updated.connect(self._on_ports_updated)
        self._scanner.sensor_found.connect(self._on_sensor_found)
        self._scanner.sensor_lost.connect(self._on_sensor_lost)

        self._build_ui()
        self._set_state_searching()
        if not self._scanner_is_shared:
            self._scanner.start()'''

if not patch_once(SCW_PATH, OLD_INIT_PATCHED, NEW_INIT_PATCHED, "__init__ patched ver"):
    patch_once(SCW_PATH, OLD_INIT_ORIG, NEW_INIT_ORIG, "__init__ orig ver")


# ─────────────────────────────────────────────────────────────────────────────
# B. _on_back и _on_start: не останавливать shared scanner
# ─────────────────────────────────────────────────────────────────────────────
print("\n[B] sensor_connect_widget.py — stop только для не-shared scanner")

patch_once(
    SCW_PATH,
    "    def _on_start(self):\n        if self._confirmed_port:\n            self._scanner.stop()\n            self.connected.emit(self._confirmed_port.device, 115200)",
    "    def _on_start(self):\n        if self._confirmed_port:\n            if not self._scanner_is_shared:\n                self._scanner.stop()\n            self.connected.emit(self._confirmed_port.device, 115200)",
    "_on_start stop",
)

patch_once(
    SCW_PATH,
    "    def _on_back(self):\n        self._scanner.stop()\n        self.back_requested.emit()",
    "    def _on_back(self):\n        if not self._scanner_is_shared:\n            self._scanner.stop()\n        self.back_requested.emit()",
    "_on_back stop",
)


# ─────────────────────────────────────────────────────────────────────────────
# C. Добавить метод sync_state в SensorConnectWidget
#    Вызывается при каждом показе экрана — подтягивает уже найденный датчик
#    или сбрасывает в состояние поиска
# ─────────────────────────────────────────────────────────────────────────────
print("\n[C] sensor_connect_widget.py — метод sync_state")

OLD_ON_BACK = "    def _on_back(self):\n        if not self._scanner_is_shared:\n            self._scanner.stop()\n        self.back_requested.emit()"

NEW_ON_BACK = '''\
    def sync_state(self):
        """Синхронизировать UI с текущим состоянием shared scanner.
        Вызывается из MainWindow при каждом показе этого экрана."""
        confirmed = self._scanner.confirmed_port
        if confirmed:
            self._confirmed_port = confirmed
            # Убедиться что порт есть в комбобоксе
            found = False
            for i in range(self._cb_port.count()):
                if self._cb_port.itemData(i) == confirmed.device:
                    self._cb_port.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                self._cb_port.addItem(
                    f"{confirmed.device}  —  {confirmed.description or 'датчик'}",
                    confirmed.device,
                )
                self._cb_port.setCurrentIndex(self._cb_port.count() - 1)
            self._set_state_connected(confirmed)
        else:
            self._confirmed_port = None
            self._set_state_searching()
            # Принудительно обновить список портов из последнего скана
            self._scanner._scan()

    def _on_back(self):
        if not self._scanner_is_shared:
            self._scanner.stop()
        self.back_requested.emit()'''

patch_once(SCW_PATH, OLD_ON_BACK, NEW_ON_BACK, "sync_state method")


# ─────────────────────────────────────────────────────────────────────────────
# D. main_window.py — _on_mode_selected: вызывать sync_state вместо start()
# ─────────────────────────────────────────────────────────────────────────────
print("\n[D] main_window.py — _on_mode_selected использует sync_state")

# Старая версия (до патча) — перезапускала scanner вручную
OLD_MODE_SENSOR = '''\
        else:
            # Перезапустить сканер при каждом входе
            self._sensor_connect._scanner.start()
            self._sensor_connect._set_state_searching()
            self._stack_exp.setCurrentIndex(1)   # → подключение датчика'''

NEW_MODE_SENSOR = '''\
        else:
            self._sensor_connect.sync_state()
            self._stack_exp.setCurrentIndex(1)   # → подключение датчика'''

if not patch_once(MW_PATH, OLD_MODE_SENSOR, NEW_MODE_SENSOR, "_on_mode_selected old"):
    # Вариант если индекс уже сдвинут нашим предыдущим патчем (IDX_CONNECT=3, стек=1)
    OLD_MODE_SENSOR2 = '''\
        else:
            # Перезапустить сканер при каждом входе
            self._sensor_connect._scanner.start()
            self._sensor_connect._set_state_searching()
            self._stack_exp.setCurrentIndex(1)'''
    NEW_MODE_SENSOR2 = '''\
        else:
            self._sensor_connect.sync_state()
            self._stack_exp.setCurrentIndex(1)'''
    if not patch_once(MW_PATH, OLD_MODE_SENSOR2, NEW_MODE_SENSOR2, "_on_mode_selected alt1"):
        # Ещё вариант — без комментария
        OLD_MODE_SENSOR3 = (
            "        else:\n"
            "            self._sensor_connect._scanner.start()\n"
            "            self._sensor_connect._set_state_searching()\n"
            "            self._stack_exp.setCurrentIndex(1)"
        )
        NEW_MODE_SENSOR3 = (
            "        else:\n"
            "            self._sensor_connect.sync_state()\n"
            "            self._stack_exp.setCurrentIndex(1)"
        )
        patch_once(MW_PATH, OLD_MODE_SENSOR3, NEW_MODE_SENSOR3, "_on_mode_selected alt2")


print("\n[fix] Готово.")
