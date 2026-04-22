"""
Патч:
  1. main.py         — запуск окна на весь экран (showMaximized)
  2. main_window.py  — если датчик уже найден при выборе «Реальный датчик»,
                       пропускаем экран подключения и сразу идём в эксперимент

Запуск из папки speedsensor_app:
    python patch_fullscreen_and_skip_connect.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(BASE, "speedsensor_app")):
    BASE = os.path.join(BASE, "speedsensor_app")
print(f"[patch] Корень проекта: {BASE}")


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


# ══════════════════════════════════════════════════════════════════════════════
# 1. main.py — showMaximized вместо show
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1] main.py — запуск на весь экран")

MAIN_PATH = os.path.join(BASE, "main.py")

patch_once(
    MAIN_PATH,
    "    window = MainWindow(settings)\n    window.show()",
    "    window = MainWindow(settings)\n    window.showMaximized()",
    "showMaximized",
)


# ══════════════════════════════════════════════════════════════════════════════
# 2. main_window.py — _on_mode_selected: если датчик уже есть → пропуск connect
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2] main_window.py — пропуск экрана подключения если датчик найден")

MW_PATH = os.path.join(BASE, "ui", "main_window.py")

# Вариант А — после patch_sensor_connect_fix.py (sync_state уже есть)
OLD_MODE_A = (
    "        else:\n"
    "            self._sensor_connect.sync_state()\n"
    "            self._stack_exp.setCurrentIndex(1)   # → подключение датчика"
)
NEW_MODE_A = (
    "        else:\n"
    "            confirmed = self._shared_scanner.confirmed_port\n"
    "            if confirmed:\n"
    "                # Датчик уже найден — сразу в эксперимент\n"
    "                self._experiment.setup(\n"
    "                    mode=MODE_SENSOR,\n"
    "                    port=confirmed.device,\n"
    "                    baud=115200,\n"
    "                    scenario=self._current_scenario,\n"
    "                )\n"
    "                self._stack_exp.setCurrentIndex(2)   # → эксперимент\n"
    "            else:\n"
    "                self._sensor_connect.sync_state()\n"
    "                self._stack_exp.setCurrentIndex(1)   # → подключение датчика"
)

# Вариант Б — если sync_state ещё не добавлен (оригинальная логика со start/searching)
OLD_MODE_B = (
    "        else:\n"
    "            # Перезапустить сканер при каждом входе\n"
    "            self._sensor_connect._scanner.start()\n"
    "            self._sensor_connect._set_state_searching()\n"
    "            self._stack_exp.setCurrentIndex(1)   # → подключение датчика"
)
NEW_MODE_B = (
    "        else:\n"
    "            confirmed = self._shared_scanner.confirmed_port\n"
    "            if confirmed:\n"
    "                # Датчик уже найден — сразу в эксперимент\n"
    "                self._experiment.setup(\n"
    "                    mode=MODE_SENSOR,\n"
    "                    port=confirmed.device,\n"
    "                    baud=115200,\n"
    "                    scenario=self._current_scenario,\n"
    "                )\n"
    "                self._stack_exp.setCurrentIndex(2)   # → эксперимент\n"
    "            else:\n"
    "                self._sensor_connect._scanner.start()\n"
    "                self._sensor_connect._set_state_searching()\n"
    "                self._stack_exp.setCurrentIndex(1)   # → подключение датчика"
)

if not patch_once(MW_PATH, OLD_MODE_A, NEW_MODE_A, "_on_mode_selected variant A"):
    patch_once(MW_PATH, OLD_MODE_B, NEW_MODE_B, "_on_mode_selected variant B")

# Проверяем что MODE_SENSOR импортирован (нужен для нового кода)
mw_text = read(MW_PATH)
if "MODE_SENSOR" not in mw_text:
    patch_once(
        MW_PATH,
        "from ui.mode_selector import ModeSelectorWidget",
        "from ui.mode_selector import ModeSelectorWidget, MODE_SENSOR, MODE_SIMULATION",
        "MODE_SENSOR import",
    )

print("\n[patch] Готово.")
