# SpeedSensor Lab

## Структура проекта

```
speedsensor_project/
├── firmware/
│   └── sensor_counter/
│       └── sensor_counter.ino   — прошивка nRF52840
├── software/
│   └── speedsensor_app/         — десктопное ПО (Python/PySide6)
│       ├── main.py
│       ├── requirements.txt
│       ├── setup_project.py     — генерирует структуру с нуля
│       ├── core/
│       ├── ui/
│       └── scenarios/
├── resume.md                    — резюме для продолжения разработки
└── README.md
```

## Быстрый старт

### Прошивка
- Плата: **Adafruit ItsyBitsy nRF52840**
- BSP: Adafruit nRF52 1.7.0
- Открыть `firmware/sensor_counter/sensor_counter.ino` в Arduino IDE
- Загрузить на плату

### ПО
```
cd software/speedsensor_app
pip install -r requirements.txt
python main.py
```

## Железо
- МК: nRF52840 ProMicro Type-C (V1940)
- Датчик: оптический датчик прерывания
- Пин датчика D0 → физический P0.22 → Arduino pin 29
- Диск: ⌀75 мм, 20 прорезей

## Serial-протокол (115200 baud)
```
Pulses: N | RPS: X.XXX | RPM: X.X | V: X.X mm/s | Pin: HIGH/LOW
```
Команды: `t` тест, `r` сброс, `i` инфо о диске, `h` помощь
