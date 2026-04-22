"""
Патч ПО:
  1. core/port_scanner.py  — добавляет sensor_serial в PortInfo, парсит "Serial:" из ответа на i
  2. ui/home_widget.py     — отображает серийный номер в карточке датчика

Запуск из папки speedsensor_app:
    python patch_sw_serial.py
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
# 1. core/port_scanner.py — sensor_serial в PortInfo + парсинг
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1] core/port_scanner.py")

SCANNER_PATH = os.path.join(BASE, "core", "port_scanner.py")

# 1a. Добавить поле в датакласс
patch_once(
    SCANNER_PATH,
    '    sensor_name: str = ""         # парсится из "Name: ..."\n'
    '    sensor_purpose: str = ""      # парсится из "Purpose: ..."\n'
    '    sensor_scenarios: str = ""    # парсится из "Scenarios: ..."',
    '    sensor_name: str = ""         # парсится из "Name: ..."\n'
    '    sensor_purpose: str = ""      # парсится из "Purpose: ..."\n'
    '    sensor_scenarios: str = ""    # парсится из "Scenarios: ..."\n'
    '    sensor_serial: str = ""       # парсится из "Serial: ..."',
    "PortInfo sensor_serial field",
)

# 1b. Парсинг Serial: в _probe_port
patch_once(
    SCANNER_PATH,
    '            name = ""\n'
    '            purpose = ""\n'
    '            scenarios = ""\n'
    '            for line in buf.splitlines():\n'
    '                ls = line.strip()\n'
    '                if ls.lower().startswith("name:"):\n'
    '                    name = ls[5:].strip()\n'
    '                elif ls.lower().startswith("purpose:"):\n'
    '                    purpose = ls[8:].strip()\n'
    '                elif ls.lower().startswith("scenarios:"):\n'
    '                    scenarios = ls[10:].strip()',
    '            name = ""\n'
    '            purpose = ""\n'
    '            scenarios = ""\n'
    '            serial_num = ""\n'
    '            for line in buf.splitlines():\n'
    '                ls = line.strip()\n'
    '                if ls.lower().startswith("serial:"):\n'
    '                    serial_num = ls[7:].strip()\n'
    '                elif ls.lower().startswith("name:"):\n'
    '                    name = ls[5:].strip()\n'
    '                elif ls.lower().startswith("purpose:"):\n'
    '                    purpose = ls[8:].strip()\n'
    '                elif ls.lower().startswith("scenarios:"):\n'
    '                    scenarios = ls[10:].strip()',
    "_probe_port parse serial",
)

# 1c. Передать serial_num в конструктор PortInfo
patch_once(
    SCANNER_PATH,
    '            return PortInfo(\n'
    '                device=device,\n'
    '                description="",\n'
    '                vid=None,\n'
    '                pid=None,\n'
    '                confirmed=True,\n'
    '                sensor_name=name,\n'
    '                sensor_purpose=purpose,\n'
    '                sensor_scenarios=scenarios,\n'
    '            )',
    '            return PortInfo(\n'
    '                device=device,\n'
    '                description="",\n'
    '                vid=None,\n'
    '                pid=None,\n'
    '                confirmed=True,\n'
    '                sensor_name=name,\n'
    '                sensor_purpose=purpose,\n'
    '                sensor_scenarios=scenarios,\n'
    '                sensor_serial=serial_num,\n'
    '            )',
    "PortInfo constructor serial",
)


# ══════════════════════════════════════════════════════════════════════════════
# 2. ui/home_widget.py — показать серийный номер в карточке
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2] ui/home_widget.py")

HOME_PATH = os.path.join(BASE, "ui", "home_widget.py")

# Добавляем строку с серийным номером после строки с портом (device)
patch_once(
    HOME_PATH,
    '        serial_lbl = QLabel(f"🔌  {port_info.device}")\n'
    '        serial_lbl.setStyleSheet(\n'
    '            f"font-size: 13px; font-weight: bold; color: {C_GREEN};"\n'
    '            " background: transparent;"\n'
    '        )\n'
    '        lay.addWidget(serial_lbl)',
    '        serial_lbl = QLabel(f"🔌  {port_info.device}")\n'
    '        serial_lbl.setStyleSheet(\n'
    '            f"font-size: 13px; font-weight: bold; color: {C_GREEN};"\n'
    '            " background: transparent;"\n'
    '        )\n'
    '        lay.addWidget(serial_lbl)\n'
    '\n'
    '        if port_info.sensor_serial:\n'
    '            sn_lbl = QLabel(f"№  {port_info.sensor_serial}")\n'
    '            sn_lbl.setStyleSheet(\n'
    '                f"font-size: 12px; color: {C_SUBTEXT}; background: transparent;"\n'
    '            )\n'
    '            lay.addWidget(sn_lbl)',
    "SensorCard serial number label",
)

print("\n[patch] Готово.")
print("Не забудьте перезалить прошивку после patch_firmware_serial.py")
print("и записать серийный номер командой:")
print('  W:<пароль>:SENSOR_SERIAL:SN-0001')
