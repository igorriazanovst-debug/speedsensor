"""
Патч: добавляет стартовую вкладку «Познайкино-НЕО» в SpeedSensor Lab.

Что делает:
  1. core/port_scanner.py  — добавляет sensor_name/purpose/scenarios в PortInfo,
                             обновляет _probe_port: парсит ответ на 'i'
  2. ui/home_widget.py     — создаёт виджет стартовой вкладки
  3. scenarios/scenarios.py— добавляет сценарий №4 «Вращательное движение»
  4. ui/main_window.py     — shared PortScanner, вкладка «Главная» первой,
                             «Сценарии» второй, остальные без изменений

Запуск из папки speedsensor_app:
    python patch_home_tab.py
"""

import os, sys

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
        print(f"  --  {os.path.relpath(path, BASE)}: маркер не найден ({label})")
        return False
    if new in text:
        print(f"  ~~  {os.path.relpath(path, BASE)}: уже применён ({label})")
        return False
    write(path, text.replace(old, new, 1))
    return True


# ══════════════════════════════════════════════════════════════════════════════
# 1. core/port_scanner.py
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1] core/port_scanner.py")

SCANNER_PATH = os.path.join(BASE, "core", "port_scanner.py")

# 1a. Расширяем PortInfo
patch_once(
    SCANNER_PATH,
    "@dataclass\nclass PortInfo:\n    device: str\n    description: str\n    vid: int | None\n    pid: int | None\n    confirmed: bool = False   # True — ответил на probe",
    "@dataclass\nclass PortInfo:\n    device: str\n    description: str\n    vid: int | None\n    pid: int | None\n    confirmed: bool = False        # True — ответил на probe\n    sensor_name: str = \"\"         # парсится из \"Name: ...\"\n    sensor_purpose: str = \"\"      # парсится из \"Purpose: ...\"\n    sensor_scenarios: str = \"\"    # парсится из \"Scenarios: ...\"",
    "PortInfo fields",
)

# 1b. PROBE_MARKER
patch_once(
    SCANNER_PATH,
    'PROBE_MARKER  = ("speedsensor", "rps:", "pulses:")   # строки в нижнем регистре',
    'PROBE_MARKER  = ("speedsensor", "rps:", "pulses:", "name:", "purpose:")   # строки в нижнем регистре',
    "PROBE_MARKER",
)

# 1c. _probe_port: возвращает PortInfo | None вместо bool, парсит Name/Purpose/Scenarios
OLD_PROBE = '''def _probe_port(device: str) -> bool:
    """Пытается открыть порт и получить ответ от прошивки."""'''

NEW_PROBE = '''def _probe_port(device: str) -> "PortInfo | None":
    """Пытается открыть порт и получить ответ от прошивки.
    Возвращает заполненный PortInfo или None."""'''

patch_once(SCANNER_PATH, OLD_PROBE, NEW_PROBE, "_probe_port signature")

# 1d. В _probe_ports: confirmed = _probe_port(...) теперь PortInfo | None
patch_once(
    SCANNER_PATH,
    "            confirmed = _probe_port(info.device)\n            if confirmed:\n                info.confirmed = True\n                with self._lock:\n                    if self._confirmed is None:\n                        self._confirmed = info\n                        self.sensor_found.emit(info)",
    "            result = _probe_port(info.device)\n            if result is not None:\n                result.confirmed = True\n                with self._lock:\n                    if self._confirmed is None:\n                        self._confirmed = result\n                        self.sensor_found.emit(result)",
    "_probe_ports body",
)

# 1e. Тело _probe_port — заменяем return True/False на парсинг и return PortInfo/None
# Ищем тело функции _probe_port целиком (после новой сигнатуры)
scanner_text = read(SCANNER_PATH)

OLD_PROBE_BODY = '''\
    try:
        with serial.Serial(device, PROBE_BAUD, timeout=PROBE_TIMEOUT) as ser:
            time.sleep(0.1)
            ser.reset_input_buffer()
            ser.write(b"\\n")
            time.sleep(0.1)
            ser.write(b"i\\n")
            deadline = time.time() + PROBE_TIMEOUT
            buf = ""
            while time.time() < deadline:
                chunk = ser.read(ser.in_waiting or 1).decode("utf-8", errors="ignore")
                buf += chunk
                if any(m in buf.lower() for m in PROBE_MARKER):
                    return True
            return False
    except Exception:
        return False'''

NEW_PROBE_BODY = '''\
    try:
        with serial.Serial(device, PROBE_BAUD, timeout=PROBE_TIMEOUT) as ser:
            time.sleep(0.1)
            ser.reset_input_buffer()
            ser.write(b"\\n")
            time.sleep(0.1)
            ser.write(b"i\\n")
            deadline = time.time() + PROBE_TIMEOUT
            buf = ""
            while time.time() < deadline:
                chunk = ser.read(ser.in_waiting or 1).decode("utf-8", errors="ignore")
                buf += chunk
                if any(m in buf.lower() for m in PROBE_MARKER):
                    break
            else:
                return None
            # Парсим идентификационные поля
            name = ""
            purpose = ""
            scenarios = ""
            for line in buf.splitlines():
                line_s = line.strip()
                if line_s.lower().startswith("name:"):
                    name = line_s[5:].strip()
                elif line_s.lower().startswith("purpose:"):
                    purpose = line_s[8:].strip()
                elif line_s.lower().startswith("scenarios:"):
                    scenarios = line_s[10:].strip()
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
# 2. scenarios/scenarios.py — добавляем сценарий №4
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2] scenarios/scenarios.py")

SCENARIOS_PATH = os.path.join(BASE, "scenarios", "scenarios.py")

SCENARIO_4 = '''\
    Scenario(
        id="rotation_demo",
        name_ru="Демонстрационная установка «Вращательное движение»",
        name_en="Rotational Motion Demo",
        description_ru="Демонстрация вращательного движения на лабораторном стенде.",
        description_en="Demonstration of rotational motion on a lab stand.",
        unit=UNIT_RAD_S,
        interval_ms=100,
        sensor=SensorConfig(sample_rate_hz=50),
    ),
'''

patch_once(
    SCENARIOS_PATH,
    "        has_simulation=True,\n    ),\n]",
    "        has_simulation=True,\n    ),\n" + SCENARIO_4 + "]",
    "scenario #4",
)


# ══════════════════════════════════════════════════════════════════════════════
# 3. ui/home_widget.py — создаём файл
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3] ui/home_widget.py")

HOME_WIDGET = '''\
"""
Стартовая вкладка «Цифровой лабораторный комплекс «Познайкино-НЕО»».

Отображает:
  • логотип (assets/logo.png, если файл существует)
  • заголовок комплекса
  • карточки подключённых датчиков (серийный номер, название, сценарии)
"""
from __future__ import annotations
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap, QFont

from core.port_scanner import PortInfo, PortScanner
from scenarios.scenarios import load_scenarios

C_BG      = "#1e1e2e"
C_SURFACE = "#181825"
C_TEXT    = "#cdd6f4"
C_SUBTEXT = "#a6adc8"
C_ACCENT  = "#cba6f7"
C_GREEN   = "#a6e3a1"
C_BLUE    = "#89b4fa"
C_BORDER  = "#45475a"

CARD_STYLE = f"""
QFrame#sensor-card {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
}}
"""


def _build_scenario_map(scenarios_dir: str) -> dict[str, tuple[int, str]]:
    """Возвращает {{scenario_id: (номер, название_ru)}}."""
    try:
        scenarios = load_scenarios(scenarios_dir)
    except Exception:
        scenarios = []
    return {sc.id: (i + 1, sc.name_ru) for i, sc in enumerate(scenarios)}


class SensorCard(QFrame):
    """Карточка одного подключённого датчика."""

    def __init__(
        self,
        port_info: PortInfo,
        scenario_map: dict[str, tuple[int, str]],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("sensor-card")
        self.setFixedWidth(340)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(CARD_STYLE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(6)

        # Серийный номер = COM-порт
        serial_lbl = QLabel(f"🔌  {port_info.device}")
        serial_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {C_GREEN};"
        )
        lay.addWidget(serial_lbl)

        # Наименование датчика
        name = port_info.sensor_name or "Датчик угловой скорости"
        name_lbl = QLabel(name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f"font-size: 14px; color: {C_TEXT};")
        lay.addWidget(name_lbl)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C_BORDER};")
        lay.addWidget(sep)

        # Сценарии
        hdr = QLabel("Сценарии экспериментов:")
        hdr.setStyleSheet(f"font-size: 12px; color: {C_SUBTEXT};")
        lay.addWidget(hdr)

        raw = port_info.sensor_scenarios  # "1,2,3" или ""
        entries = [s.strip() for s in raw.split(",") if s.strip()] if raw else []

        if entries:
            for entry in entries:
                matched = None
                for sc_id, (num, sc_name) in scenario_map.items():
                    if entry == str(num) or entry == sc_id:
                        matched = f"  •  №{num}  {sc_name}"
                        break
                lbl = QLabel(matched or f"  •  Сценарий {entry}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"font-size: 12px; color: {C_TEXT};")
                lay.addWidget(lbl)
        else:
            no_sc = QLabel("  —")
            no_sc.setStyleSheet(f"font-size: 12px; color: {C_SUBTEXT};")
            lay.addWidget(no_sc)

        lay.addStretch()


class HomeWidget(QWidget):
    """Стартовая вкладка приложения."""

    def __init__(self, scanner: PortScanner, scenarios_dir: str = "", parent=None):
        super().__init__(parent)
        self._scanner = scanner
        self._scenarios_dir = scenarios_dir
        self._scenario_map: dict[str, tuple[int, str]] = {}

        self._build_ui()
        self._reload_scenario_map()

        self._scanner.sensor_found.connect(self._on_update)
        self._scanner.sensor_lost.connect(self._on_update)
        self._scanner.ports_updated.connect(self._on_update)

    def _reload_scenario_map(self):
        self._scenario_map = _build_scenario_map(self._scenarios_dir)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet(f"background: {C_BG};")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 32, 40, 32)
        lay.setSpacing(16)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Логотип
        logo_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")
        )
        if os.path.isfile(logo_path):
            logo_lbl = QLabel()
            pix = QPixmap(logo_path)
            logo_lbl.setPixmap(
                pix.scaledToHeight(160, Qt.TransformationMode.SmoothTransformation)
            )
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(logo_lbl)
        else:
            ph = QLabel("[Логотип: assets/logo.png]")
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ph.setFixedHeight(160)
            ph.setStyleSheet(
                f"color: {C_SUBTEXT}; font-size: 13px;"
                f" border: 2px dashed {C_BORDER}; border-radius: 8px;"
            )
            lay.addWidget(ph)

        # Заголовок
        title = QLabel("Цифровой лабораторный комплекс «Познайкино-НЕО»")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_ACCENT}; margin-bottom: 8px;")
        lay.addWidget(title)

        # Секция датчиков
        sec = QLabel("Подключённые датчики")
        sec.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {C_BLUE}; margin-top: 12px;"
        )
        lay.addWidget(sec)

        # Контейнер карточек
        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet("background: transparent;")
        self._cards_lay = QHBoxLayout(self._cards_widget)
        self._cards_lay.setContentsMargins(0, 0, 0, 0)
        self._cards_lay.setSpacing(16)
        self._cards_lay.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        lay.addWidget(self._cards_widget)

        self._no_sensors_lbl = QLabel(
            "Датчики не обнаружены. Подключите датчик к USB."
        )
        self._no_sensors_lbl.setStyleSheet(
            f"font-size: 14px; color: {C_SUBTEXT};"
        )
        self._no_sensors_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._no_sensors_lbl)

        lay.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

        self._refresh_cards()

    @Slot()
    def _on_update(self, *args):
        self._refresh_cards()

    def _refresh_cards(self):
        while self._cards_lay.count():
            item = self._cards_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ports: list[PortInfo] = []
        confirmed = self._scanner.confirmed_port
        if confirmed:
            ports.append(confirmed)

        if ports:
            self._no_sensors_lbl.hide()
            for pi in ports:
                self._cards_lay.addWidget(SensorCard(pi, self._scenario_map))
            self._cards_lay.addStretch()
        else:
            self._no_sensors_lbl.show()
'''

write(os.path.join(BASE, "ui", "home_widget.py"), HOME_WIDGET)


# ══════════════════════════════════════════════════════════════════════════════
# 4. ui/main_window.py — shared PortScanner + вкладка «Главная» первой
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4] ui/main_window.py")

MW_PATH = os.path.join(BASE, "ui", "main_window.py")

# 4a. Импорты
patch_once(
    MW_PATH,
    "from ui.scenarios_widget import ScenariosWidget\nfrom ui.mode_selector import ModeSelectorWidget, MODE_SENSOR, MODE_SIMULATION\nfrom ui.sensor_connect_widget import SensorConnectWidget\nfrom ui.experiment_widget import ExperimentWidget",
    "import os\n\nfrom ui.scenarios_widget import ScenariosWidget\nfrom ui.mode_selector import ModeSelectorWidget, MODE_SENSOR, MODE_SIMULATION\nfrom ui.sensor_connect_widget import SensorConnectWidget\nfrom ui.experiment_widget import ExperimentWidget\nfrom ui.home_widget import HomeWidget\nfrom core.port_scanner import PortScanner",
    "imports",
)

# 4b. Константы индексов вкладок
patch_once(
    MW_PATH,
    "IDX_SCENARIOS = 0\nIDX_MODE      = 1\nIDX_CONNECT   = 2\nIDX_EXPERIMENT = 3",
    "IDX_HOME       = 0\nIDX_SCENARIOS  = 1\nIDX_MODE       = 2\nIDX_CONNECT    = 3\nIDX_EXPERIMENT = 4",
    "IDX constants",
)

# 4c. В _build_ui: создать shared PortScanner и передать в SensorConnectWidget.
#     Вставляем HomeWidget до «Сценарии».
#     SensorConnectWidget должен принять внешний scanner.
#
#     Ищем место создания self._tabs и добавляем HomeWidget первой вкладкой.

patch_once(
    MW_PATH,
    "        # ── Tabs (верхние вкладки только для навигации) ───────────────────\n        self._tabs = QTabWidget()\n        self._tabs.setTabPosition(QTabWidget.TabPosition.North)\n        self._tabs.currentChanged.connect(self._on_tab_changed)\n\n        # Вкладка «Сценарии»",
    "        # ── Tabs (верхние вкладки только для навигации) ───────────────────\n        self._tabs = QTabWidget()\n        self._tabs.setTabPosition(QTabWidget.TabPosition.North)\n        self._tabs.currentChanged.connect(self._on_tab_changed)\n\n        # Shared PortScanner (используется HomeWidget и SensorConnectWidget)\n        self._shared_scanner = PortScanner(self)\n        self._shared_scanner.start()\n\n        # Вкладка «Главная»\n        _scenarios_dir = os.path.join(os.path.dirname(__file__), \"..\", \"scenarios\")\n        self._home_widget = HomeWidget(self._shared_scanner, _scenarios_dir)\n        self._tabs.addTab(self._home_widget, \"🏠  Главная\")\n\n        # Вкладка «Сценарии»",
    "_tabs creation + HomeWidget tab",
)

# 4d. Обновить _on_lang_changed — добавить «Главная» в списки вкладок
patch_once(
    MW_PATH,
    '        tab_ru = ["📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]\n        tab_en = ["📋  Scenarios", "📈  Experiment",  "🔬  Processing", "🌊  Fluid Sim"]',
    '        tab_ru = ["🏠  Главная", "📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]\n        tab_en = ["🏠  Home",    "📋  Scenarios", "📈  Experiment",  "🔬  Processing", "🌊  Fluid Sim"]',
    "lang tab labels",
)

# Альтернативный формат строк lang (другая версия main_window)
patch_once(
    MW_PATH,
    '        tab_ru = ["📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]\n        tab_en = ["📋  Scenarios", "📈  Experiment",  "🔬  Processing", "🌊  Simulation"]',
    '        tab_ru = ["🏠  Главная", "📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]\n        tab_en = ["🏠  Home",    "📋  Scenarios", "📈  Experiment",  "🔬  Processing", "🌊  Simulation"]',
    "lang tab labels (alt)",
)

# 4e. _on_scenario_launched: переключаться на вкладку 2 (Эксперимент), а не 1
patch_once(
    MW_PATH,
    "        self._stack_exp.setCurrentIndex(0)   # показать выбор режима\n        self._tabs.setCurrentIndex(1)         # переключить на вкладку эксперимента",
    "        self._stack_exp.setCurrentIndex(0)   # показать выбор режима\n        self._tabs.setCurrentIndex(2)         # переключить на вкладку эксперимента",
    "scenario launch tab switch",
)

# Альтернативный вариант (без комментариев)
patch_once(
    MW_PATH,
    "        self._tabs.setCurrentIndex(1)",
    "        self._tabs.setCurrentIndex(2)",
    "tab switch alt",
)

print("\n[patch] Готово.")
