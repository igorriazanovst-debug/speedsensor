"""
Патч прошивки sensor_counter.ino:
  - добавляет #include "sensor_config.h"
  - убирает DEFAULT_NAME/PURPOSE/SCENARIOS (теперь они в sensor_config.h)
  - добавляет g_sensor_serial, формируемый из FICR UID + SENSOR_INSTANCE
  - loadMeta читает серийник из flash; если пусто — берёт из FICR+config,
    записывает в flash (один раз при первом старте)
  - printSensorInfo выводит Serial:
  - handleWrite принимает (но игнорирует) попытку изменить серийник — он read-only

Запуск из папки рядом с firmware/:
    python patch_firmware_serial_ficr.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))

# Ищем .ino
CANDIDATES = [
    os.path.join(BASE, "firmware", "sensor_counter", "sensor_counter.ino"),
    os.path.join(BASE, "..", "firmware", "sensor_counter", "sensor_counter.ino"),
    os.path.join(BASE, "sensor_counter", "sensor_counter.ino"),
    os.path.join(BASE, "sensor_counter.ino"),
]
INO_PATH = None
for c in CANDIDATES:
    if os.path.isfile(os.path.normpath(c)):
        INO_PATH = os.path.normpath(c)
        break

if INO_PATH is None:
    print("ОШИБКА: sensor_counter.ino не найден. Укажите путь в переменной INO_PATH.")
    exit(1)

INO_DIR = os.path.dirname(INO_PATH)
CONFIG_PATH = os.path.join(INO_DIR, "sensor_config.h")

print(f"[patch] Прошивка : {INO_PATH}")
print(f"[patch] Конфиг   : {CONFIG_PATH}")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  OK  {os.path.basename(path)}")

def patch_once(path, old, new, label=""):
    text = read(path)
    if old not in text:
        print(f"  --  не найден ({label})")
        return False
    if new in text:
        print(f"  ~~  уже применён ({label})")
        return False
    write(path, text.replace(old, new, 1))
    return True


# ══════════════════════════════════════════════════════════════════════════════
# 1. Создать sensor_config.h рядом с .ino (если не существует)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1] sensor_config.h")

CONFIG_CONTENT = """\
// =============================================================================
// sensor_config.h — конфигурация экземпляра датчика
//
// Редактировать перед прошивкой каждого устройства:
//   SENSOR_INSTANCE — порядковый номер экземпляра: "0001", "0002", ...
//
// Серийный номер формируется автоматически:
//   Serial = <FICR Unique ID>-<SENSOR_INSTANCE>
//
// Остальные поля — значения по умолчанию, записываются в flash при первом старте.
// Можно изменить через команду W:<пароль>:<ключ>:<значение> по Serial.
// =============================================================================

#define SENSOR_INSTANCE   "0001"

#define CFG_NAME       "Датчик угловой скорости"
#define CFG_PURPOSE    "Измерение угловой скорости"
#define CFG_SCENARIOS  "1,2,3,4"
"""

if not os.path.isfile(CONFIG_PATH):
    write(CONFIG_PATH, CONFIG_CONTENT)
else:
    print(f"  ~~  sensor_config.h уже существует — не перезаписываем")


# ══════════════════════════════════════════════════════════════════════════════
# 2. Патч sensor_counter.ino
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2] sensor_counter.ino")

# 2a. Добавить #include "sensor_config.h" после #include <Adafruit_LittleFS.h>
patch_once(
    INO_PATH,
    '#include <Adafruit_LittleFS.h>',
    '#include <Adafruit_LittleFS.h>\n#include "sensor_config.h"',
    "include sensor_config.h",
)

# 2b. Добавить KEY_SERIAL
patch_once(
    INO_PATH,
    '#define KEY_SCENARIOS "SENSOR_SCENARIOS"',
    '#define KEY_SCENARIOS "SENSOR_SCENARIOS"\n#define KEY_SERIAL    "SENSOR_SERIAL"',
    "KEY_SERIAL",
)

# 2c. Заменить DEFAULT_* на ссылки на CFG_* из sensor_config.h
patch_once(
    INO_PATH,
    '// Значения по умолчанию (если файл не найден или поле отсутствует)\n'
    '#define DEFAULT_NAME      "Датчик угловой скорости"\n'
    '#define DEFAULT_PURPOSE   "Измерение угловой скорости"\n'
    '#define DEFAULT_SCENARIOS "1,2,3,4"',
    '// Значения по умолчанию берутся из sensor_config.h\n'
    '#define DEFAULT_NAME      CFG_NAME\n'
    '#define DEFAULT_PURPOSE   CFG_PURPOSE\n'
    '#define DEFAULT_SCENARIOS CFG_SCENARIOS',
    "DEFAULT_* → CFG_* (1,2,3,4)",
)
# Альтернатива если DEFAULT_SCENARIOS "1,2,3"
patch_once(
    INO_PATH,
    '// Значения по умолчанию (если файл не найден или поле отсутствует)\n'
    '#define DEFAULT_NAME      "Датчик угловой скорости"\n'
    '#define DEFAULT_PURPOSE   "Измерение угловой скорости"\n'
    '#define DEFAULT_SCENARIOS "1,2,3"',
    '// Значения по умолчанию берутся из sensor_config.h\n'
    '#define DEFAULT_NAME      CFG_NAME\n'
    '#define DEFAULT_PURPOSE   CFG_PURPOSE\n'
    '#define DEFAULT_SCENARIOS CFG_SCENARIOS',
    "DEFAULT_* → CFG_* (1,2,3)",
)

# 2d. Добавить глобальную переменную g_sensor_serial
patch_once(
    INO_PATH,
    'String g_sensor_name;\nString g_sensor_purpose;\nString g_sensor_scenarios;',
    'String g_sensor_name;\nString g_sensor_purpose;\nString g_sensor_scenarios;\nString g_sensor_serial;',
    "g_sensor_serial global",
)

# 2e. Добавить функцию buildSerial() перед loadMeta
# Вставляем перед void loadMeta()
OLD_LOAD_META_BEGIN = 'void loadMeta() {'
NEW_LOAD_META_BEGIN = '''\
// -------------------------------------------------- Serial number --

// Читает 64-битный уникальный ID из FICR и возвращает HEX-строку (16 символов)
String readFICR() {
  uint32_t lo = NRF_FICR->DEVICEID[0];
  uint32_t hi = NRF_FICR->DEVICEID[1];
  char buf[17];
  snprintf(buf, sizeof(buf), "%08X%08X", (unsigned int)hi, (unsigned int)lo);
  return String(buf);
}

// Формирует серийный номер: <FICR_ID>-<SENSOR_INSTANCE>
String buildSerial() {
  return readFICR() + "-" + SENSOR_INSTANCE;
}

void loadMeta() {'''

patch_once(INO_PATH, OLD_LOAD_META_BEGIN, NEW_LOAD_META_BEGIN, "buildSerial function")

# 2f. loadMeta: добавить инициализацию g_sensor_serial и чтение из flash
patch_once(
    INO_PATH,
    '  g_sensor_name      = DEFAULT_NAME;\n'
    '  g_sensor_purpose   = DEFAULT_PURPOSE;\n'
    '  g_sensor_scenarios = DEFAULT_SCENARIOS;',
    '  g_sensor_name      = DEFAULT_NAME;\n'
    '  g_sensor_purpose   = DEFAULT_PURPOSE;\n'
    '  g_sensor_scenarios = DEFAULT_SCENARIOS;\n'
    '  g_sensor_serial    = buildSerial();   // всегда вычисляется из FICR',
    "loadMeta g_sensor_serial init",
)

# 2g. loadMeta: после парсинга KEY_SCENARIOS добавить чтение KEY_SERIAL из flash
#     (если в flash есть — используем, иначе остаётся buildSerial())
patch_once(
    INO_PATH,
    '  v = parseField(content, KEY_SCENARIOS); if (v.length()) g_sensor_scenarios = v;\n}',
    '  v = parseField(content, KEY_SCENARIOS); if (v.length()) g_sensor_scenarios = v;\n'
    '  // Серийник из flash (если был записан ранее); иначе остаётся buildSerial()\n'
    '  v = parseField(content, KEY_SERIAL);    if (v.length()) g_sensor_serial = v;\n}',
    "loadMeta parse KEY_SERIAL",
)

# 2h. saveMeta: сохранять серийник в flash
patch_once(
    INO_PATH,
    '  content = setField(content, KEY_NAME,      g_sensor_name);\n'
    '  content = setField(content, KEY_PURPOSE,   g_sensor_purpose);\n'
    '  content = setField(content, KEY_SCENARIOS, g_sensor_scenarios);',
    '  content = setField(content, KEY_NAME,      g_sensor_name);\n'
    '  content = setField(content, KEY_PURPOSE,   g_sensor_purpose);\n'
    '  content = setField(content, KEY_SCENARIOS, g_sensor_scenarios);\n'
    '  content = setField(content, KEY_SERIAL,    g_sensor_serial);',
    "saveMeta KEY_SERIAL",
)

# 2i. printSensorInfo: вывести серийный номер первым
patch_once(
    INO_PATH,
    '  Serial.println("--- SENSOR INFO ---");\n'
    '  Serial.print("Name: ");      Serial.println(g_sensor_name);\n'
    '  Serial.print("Purpose: ");   Serial.println(g_sensor_purpose);\n'
    '  Serial.print("Scenarios: "); Serial.println(g_sensor_scenarios);',
    '  Serial.println("--- SENSOR INFO ---");\n'
    '  Serial.print("Serial: ");    Serial.println(g_sensor_serial);\n'
    '  Serial.print("Name: ");      Serial.println(g_sensor_name);\n'
    '  Serial.print("Purpose: ");   Serial.println(g_sensor_purpose);\n'
    '  Serial.print("Scenarios: "); Serial.println(g_sensor_scenarios);',
    "printSensorInfo Serial:",
)

# 2j. handleWrite: серийник read-only — молча игнорируем попытку записи
patch_once(
    INO_PATH,
    '  if (key == KEY_NAME)           g_sensor_name = value;\n'
    '  else if (key == KEY_PURPOSE)   g_sensor_purpose = value;\n'
    '  else if (key == KEY_SCENARIOS) g_sensor_scenarios = value;\n'
    '  else return; // неизвестный ключ — молчим',
    '  if (key == KEY_NAME)           g_sensor_name = value;\n'
    '  else if (key == KEY_PURPOSE)   g_sensor_purpose = value;\n'
    '  else if (key == KEY_SCENARIOS) g_sensor_scenarios = value;\n'
    '  else if (key == KEY_SERIAL)    return; // серийник read-only\n'
    '  else return; // неизвестный ключ — молчим',
    "handleWrite KEY_SERIAL read-only",
)

# 2k. printHelp: обновить список ключей
patch_once(
    INO_PATH,
    '  Serial.println("    ключи: SENSOR_NAME | SENSOR_PURPOSE | SENSOR_SCENARIOS");',
    '  Serial.println("    ключи: SENSOR_NAME | SENSOR_PURPOSE | SENSOR_SCENARIOS");'
    '\n  Serial.println("    (SENSOR_SERIAL формируется автоматически, изменить нельзя)");',
    "printHelp keys",
)

print("\n[patch] Готово.")
print(f"\nПеред прошивкой каждого экземпляра датчика откройте:")
print(f"  {CONFIG_PATH}")
print(f"и измените SENSOR_INSTANCE на нужный номер (0001, 0002, ...).")
print(f"\nСерийный номер будет: <16-символьный FICR ID>-<SENSOR_INSTANCE>")
