#include <Adafruit_TinyUSB.h>
#include <InternalFileSystem.h>
#include <Adafruit_LittleFS.h>

using namespace Adafruit_LittleFS_Namespace;

// === Параметры диска ===
#define SENSOR_PIN      29
#define SLOTS           20
#define SLOT_WIDTH_MM   5.0f
#define GAP_WIDTH_MM    6.0f
#define DISK_DIAM_MM    75.0f
#define REPORT_MS       100

// === Идентификация датчика ===
// Пароль задаётся здесь, на этапе компиляции. По Serial никогда не передаётся.
#define ADMIN_PASSWORD  "karamba"
#define META_FILE       "/sensor_meta.txt"

#define KEY_NAME      "SENSOR_NAME"
#define KEY_PURPOSE   "SENSOR_PURPOSE"
#define KEY_SCENARIOS "SENSOR_SCENARIOS"

// Значения по умолчанию (если файл не найден или поле отсутствует)
#define DEFAULT_NAME      "Датчик угловой скорости"
#define DEFAULT_PURPOSE   "Измерение угловой скорости"
#define DEFAULT_SCENARIOS "1,2,3,4"

// === Period-based measurement ===
#define PULSE_BUF_SIZE  8        // усреднение по 8 последним импульсам
#define TIMEOUT_US      500000UL // 500 мс без импульсов → RPS = 0

// ===========================

// Кольцевой буфер меток времени импульсов (микросекунды)
volatile uint32_t pulseTimes[PULSE_BUF_SIZE];
volatile uint8_t  pulseBufHead  = 0;
volatile uint8_t  pulseBufCount = 0;
volatile uint32_t lastPulseUs   = 0;

uint32_t lastReport = 0;

String g_sensor_name;
String g_sensor_purpose;
String g_sensor_scenarios;

// -------------------------------------------------- Flash helpers --

// Читает значение по ключу из строки вида "KEY=VALUE\n..."
String parseField(const String& content, const String& key) {
  String search = key + "=";
  int idx = content.indexOf(search);
  if (idx < 0) return "";
  int start = idx + search.length();
  int end = content.indexOf('\n', start);
  if (end < 0) end = content.length();
  String val = content.substring(start, end);
  val.trim();
  return val;
}

// Заменяет или добавляет KEY=VALUE в строке content
String setField(const String& content, const String& key, const String& value) {
  String search = key + "=";
  String newLine = key + "=" + value + "\n";
  int idx = content.indexOf(search);
  if (idx < 0) {
    return content + newLine;
  }
  int end = content.indexOf('\n', idx);
  if (end < 0) end = content.length();
  return content.substring(0, idx) + newLine + content.substring(end + 1);
}

void loadMeta() {
  g_sensor_name      = DEFAULT_NAME;
  g_sensor_purpose   = DEFAULT_PURPOSE;
  g_sensor_scenarios = DEFAULT_SCENARIOS;

  File file(InternalFS);
  if (!file.open(META_FILE, FILE_O_READ)) return;

  String content = "";
  while (file.available()) {
    content += (char)file.read();
  }
  file.close();

  String v;
  v = parseField(content, KEY_NAME);      if (v.length()) g_sensor_name = v;
  v = parseField(content, KEY_PURPOSE);   if (v.length()) g_sensor_purpose = v;
  v = parseField(content, KEY_SCENARIOS); if (v.length()) g_sensor_scenarios = v;
}

bool saveMeta() {
  // Читаем текущее содержимое
  String content = "";
  File rf(InternalFS);
  if (rf.open(META_FILE, FILE_O_READ)) {
    while (rf.available()) content += (char)rf.read();
    rf.close();
  }

  // Обновляем все поля
  content = setField(content, KEY_NAME,      g_sensor_name);
  content = setField(content, KEY_PURPOSE,   g_sensor_purpose);
  content = setField(content, KEY_SCENARIOS, g_sensor_scenarios);

  // Удаляем старый файл и пишем новый
  InternalFS.remove(META_FILE);
  File wf(InternalFS);
  if (!wf.open(META_FILE, FILE_O_WRITE)) return false;
  wf.print(content);
  wf.close();
  return true;
}

// -------------------------------------------------- Serial print --

void printHelp() {
  Serial.println("---");
  Serial.println("Команды:");
  Serial.println("  t                        - тест пина");
  Serial.println("  r                        - сброс счётчика");
  Serial.println("  i                        - информация о датчике и диске");
  Serial.println("  h                        - помощь");
  Serial.println("  W:<pw>:<key>:<value>     - записать поле (требует пароль)");
  Serial.println("    ключи: SENSOR_NAME | SENSOR_PURPOSE | SENSOR_SCENARIOS");
  Serial.println("---");
}

void printSensorInfo() {
  Serial.println("--- SENSOR INFO ---");
  Serial.print("Name: ");      Serial.println(g_sensor_name);
  Serial.print("Purpose: ");   Serial.println(g_sensor_purpose);
  Serial.print("Scenarios: "); Serial.println(g_sensor_scenarios);
  Serial.println("--- DISK INFO ---");
  Serial.print("Диаметр: ");    Serial.print(DISK_DIAM_MM);    Serial.println(" мм");
  Serial.print("Прорезей: ");   Serial.println(SLOTS);
  Serial.print("Прорезь: ");    Serial.print(SLOT_WIDTH_MM);   Serial.println(" мм");
  Serial.print("Промежуток: "); Serial.print(GAP_WIDTH_MM);    Serial.println(" мм");
  Serial.print("Период: ");     Serial.print(SLOT_WIDTH_MM + GAP_WIDTH_MM); Serial.println(" мм");
  Serial.println("-----------------");
}

// -------------------------------------------------- Write command --
// Формат: W:<пароль>:<ключ>:<значение>
// Значение может содержать двоеточия. Разбиваем только первые 3 разделителя.

void handleWrite(const String& line) {
  // line уже без ведущего 'W'
  // Ожидаем: :<pw>:<key>:<value>
  if (line.length() < 2 || line[0] != ':') return;

  String rest = line.substring(1); // <pw>:<key>:<value>
  int sep1 = rest.indexOf(':');
  if (sep1 < 0) return;

  String pw  = rest.substring(0, sep1);
  String tail = rest.substring(sep1 + 1); // <key>:<value>

  // Проверяем пароль — никакого ответа при ошибке
  if (!pw.equals(ADMIN_PASSWORD)) return;

  int sep2 = tail.indexOf(':');
  if (sep2 < 0) return;

  String key   = tail.substring(0, sep2);
  String value = tail.substring(sep2 + 1);
  key.trim();
  value.trim();

  if (key == KEY_NAME)           g_sensor_name = value;
  else if (key == KEY_PURPOSE)   g_sensor_purpose = value;
  else if (key == KEY_SCENARIOS) g_sensor_scenarios = value;
  else return; // неизвестный ключ — молчим

  if (saveMeta()) {
    Serial.println("[OK]");
  }
  // При ошибке записи — молчим (не раскрываем информацию)
}


// -------------------------------------------------- ISR --

void onPulse() {
  uint32_t t = micros();
  pulseTimes[pulseBufHead] = t;
  pulseBufHead = (pulseBufHead + 1) % PULSE_BUF_SIZE;
  if (pulseBufCount < PULSE_BUF_SIZE) pulseBufCount++;
  lastPulseUs = t;
}

// -------------------------------------------------- RPS calculation --

// Вычисляет RPS по кольцевому буферу меток времени.
// Возвращает 0 если данных нет или таймаут.
float calcRPS() {
  noInterrupts();
  uint8_t  count      = pulseBufCount;
  uint32_t lastPulse  = lastPulseUs;
  uint8_t  head       = pulseBufHead;

  // Копируем буфер
  uint32_t buf[PULSE_BUF_SIZE];
  for (uint8_t i = 0; i < PULSE_BUF_SIZE; i++) buf[i] = pulseTimes[i];
  interrupts();

  // Таймаут: давно не было импульсов
  if (count == 0) return 0.0f;
  if ((uint32_t)(micros() - lastPulse) > TIMEOUT_US) return 0.0f;

  // Нужно минимум 2 точки для вычисления периода
  if (count < 2) return 0.0f;

  // Индексы: самый старый и самый новый элемент в кольцевом буфере
  uint8_t n        = count < PULSE_BUF_SIZE ? count : PULSE_BUF_SIZE;
  uint8_t newestIdx = (head + PULSE_BUF_SIZE - 1) % PULSE_BUF_SIZE;
  uint8_t oldestIdx = (head + PULSE_BUF_SIZE - n) % PULSE_BUF_SIZE;

  uint32_t newest = buf[newestIdx];
  uint32_t oldest = buf[oldestIdx];

  // Интервал между крайними точками (мкс), n-1 периодов между n импульсами
  uint32_t spanUs = newest - oldest; // uint32 корректно обрабатывает переполнение
  if (spanUs == 0) return 0.0f;

  // Среднее время одного периода диска (один оборот = SLOTS импульсов)
  // period_per_slot_us = spanUs / (n - 1)
  // rps = 1 / (period_per_slot_us * SLOTS / 1e6)
  float rps = (float)(n - 1) * 1e6f / ((float)spanUs * SLOTS);
  return rps;
}

// -------------------------------------------------- Setup --

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  InternalFS.begin();
  loadMeta();

  pinMode(SENSOR_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN), onPulse, FALLING);

  Serial.println("=== RPM Counter Ready ===");
  printSensorInfo();

  int pinState = digitalRead(SENSOR_PIN);
  Serial.println(pinState == HIGH ? "Pin: HIGH (луч свободен)" : "Pin: LOW (луч перекрыт)");

  printHelp();
  lastReport = millis();
}

// -------------------------------------------------- Loop --

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.length() == 0) {
      // пустая строка — игнорируем
    } else if (line[0] == 't') {
      noInterrupts();
      uint32_t lp = lastPulseUs;
      uint8_t  bc = pulseBufCount;
      interrupts();
      int pinState = digitalRead(SENSOR_PIN);
      Serial.print("[TEST] Pin=");
      Serial.print(pinState == HIGH ? "HIGH (свободно)" : "LOW (перекрыто)");
      Serial.print(" | Импульсов в буфере: ");
      Serial.print(bc);
      Serial.print(" | RPS: ");
      Serial.println(calcRPS(), 3);
    } else if (line[0] == 'r') {
      noInterrupts();
      pulseBufCount = 0;
      pulseBufHead  = 0;
      lastPulseUs   = 0;
      interrupts();
      Serial.println("[RESET] Счётчик сброшен.");
    } else if (line[0] == 'i') {
      printSensorInfo();
    } else if (line[0] == 'h') {
      printHelp();
    } else if (line[0] == 'W') {
      handleWrite(line.substring(1));
    }
  }

  uint32_t now     = millis();
  uint32_t elapsed = now - lastReport;

  if (elapsed >= REPORT_MS) {
    lastReport = now;

    float rps          = calcRPS();
    float rpm          = rps * 60.0f;
    float circumference = 3.14159f * DISK_DIAM_MM;
    float linear_mm_s  = circumference * rps;

    // Pulses: поле оставляем для совместимости с ПО, выводим накопленный счёт в буфере
    noInterrupts();
    uint8_t bc = pulseBufCount;
    interrupts();

    Serial.print("Pulses: ");  Serial.print(bc);
    Serial.print(" | RPS: ");  Serial.print(rps, 3);
    Serial.print(" | RPM: ");  Serial.print(rpm, 1);
    Serial.print(" | V: ");    Serial.print(linear_mm_s, 1);
    Serial.print(" mm/s | Pin: ");
    Serial.println(digitalRead(SENSOR_PIN) == HIGH ? "HIGH" : "LOW");
  }
}
