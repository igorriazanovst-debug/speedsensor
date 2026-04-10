#include <Adafruit_TinyUSB.h>

// === Параметры диска ===
#define SENSOR_PIN      29
#define SLOTS           20      // количество прорезей
#define SLOT_WIDTH_MM   5.0f    // ширина прорези, мм
#define GAP_WIDTH_MM    6.0f    // ширина промежутка, мм
#define DISK_DIAM_MM    75.0f   // диаметр диска, мм
#define REPORT_MS       500

// Длина окружности
// Один период = прорезь + промежуток = 11 мм
// Проверка: 20 * 11 = 220 мм, длина окружности = PI * 75 = 235.6 мм — допустимо

volatile uint32_t pulseCount = 0;
uint32_t lastReport = 0;

void onPulse() {
  pulseCount++;
}

void printHelp() {
  Serial.println("---");
  Serial.println("Команды:");
  Serial.println("  t - тест пина");
  Serial.println("  r - сброс счётчика");
  Serial.println("  i - информация о диске");
  Serial.println("  h - помощь");
  Serial.println("---");
}

void printDiskInfo() {
  Serial.println("--- DISK INFO ---");
  Serial.print("Диаметр: ");    Serial.print(DISK_DIAM_MM);    Serial.println(" мм");
  Serial.print("Прорезей: ");   Serial.println(SLOTS);
  Serial.print("Прорезь: ");    Serial.print(SLOT_WIDTH_MM);   Serial.println(" мм");
  Serial.print("Промежуток: "); Serial.print(GAP_WIDTH_MM);    Serial.println(" мм");
  Serial.print("Период: ");     Serial.print(SLOT_WIDTH_MM + GAP_WIDTH_MM); Serial.println(" мм");
  Serial.println("-----------------");
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  pinMode(SENSOR_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN), onPulse, FALLING);

  Serial.println("=== RPM Counter Ready ===");
  printDiskInfo();

  int pinState = digitalRead(SENSOR_PIN);
  Serial.println(pinState == HIGH ? "Pin: HIGH (луч свободен)" : "Pin: LOW (луч перекрыт)");

  printHelp();
  lastReport = millis();
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 't') {
      noInterrupts();
      uint32_t cnt = pulseCount;
      interrupts();
      int pinState = digitalRead(SENSOR_PIN);
      Serial.print("[TEST] Pin=");
      Serial.print(pinState == HIGH ? "HIGH (свободно)" : "LOW (перекрыто)");
      Serial.print(" | Импульсов: ");
      Serial.println(cnt);
    } else if (cmd == 'r') {
      noInterrupts();
      pulseCount = 0;
      interrupts();
      Serial.println("[RESET] Счётчик сброшен.");
    } else if (cmd == 'i') {
      printDiskInfo();
    } else if (cmd == 'h') {
      printHelp();
    }
  }

  uint32_t now = millis();
  uint32_t elapsed = now - lastReport;

  if (elapsed >= REPORT_MS) {
    lastReport = now;

    noInterrupts();
    uint32_t count = pulseCount;
    pulseCount = 0;
    interrupts();

    float rps = (float)count / SLOTS / (elapsed / 1000.0f);
    float rpm = rps * 60.0f;

    // Линейная скорость на краю диска: v = pi * d * rps
    float circumference = 3.14159f * DISK_DIAM_MM;
    float linear_mm_s = circumference * rps;

    Serial.print("Pulses: ");   Serial.print(count);
    Serial.print(" | RPS: ");   Serial.print(rps, 3);
    Serial.print(" | RPM: ");   Serial.print(rpm, 1);
    Serial.print(" | V: ");     Serial.print(linear_mm_s, 1);
    Serial.print(" mm/s | Pin: ");
    Serial.println(digitalRead(SENSOR_PIN) == HIGH ? "HIGH" : "LOW");
  }
}
