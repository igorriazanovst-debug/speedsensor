"""
Создаёт структуру проекта speedsensor_app в текущей папке.
Запуск: python setup_project.py
"""

import os

DIRS = [
    "core",
    "ui",
    "ui/widgets",
    "scenarios",
    "locales",
    "assets",
]

INIT_PACKAGES = ["core", "ui", "scenarios"]

FILES = {
    "core/__init__.py": "",
    "ui/__init__.py": "",
    "scenarios/__init__.py": "",

    "requirements.txt": (
        "PySide6>=6.6.0\n"
        "pyserial>=3.5\n"
    ),

    "main.py": '''\
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator
from ui.main_window import MainWindow
from core.settings import AppSettings

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SpeedSensor Lab")
    app.setOrganizationName("SpeedSensorLab")

    settings = AppSettings()

    translator = QTranslator()
    lang = settings.get("language", "ru")
    translator.load(f"locales/{lang}.qm")
    app.installTranslator(translator)

    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
''',

    "core/settings.py": '''\
from PySide6.QtCore import QSettings


class AppSettings:
    def __init__(self):
        self._qs = QSettings("SpeedSensorLab", "SpeedSensorApp")

    def get(self, key: str, default=None):
        return self._qs.value(key, default)

    def set(self, key: str, value):
        self._qs.setValue(key, value)
        self._qs.sync()

    def get_all(self) -> dict:
        result = {}
        for key in self._qs.allKeys():
            result[key] = self._qs.value(key)
        return result
''',

    "core/serial_utils.py": '''\
import serial.tools.list_ports


def list_serial_ports() -> list[str]:
    ports = serial.tools.list_ports.comports()
    return [p.device for p in sorted(ports, key=lambda x: x.device)]
''',

    "scenarios/scenarios.py": '''\
from dataclasses import dataclass, field
from typing import Optional
import json
import os

UNIT_RAD_S = "rad/s"
UNIT_RPS = "rps"

ROLE_RESEARCHER = "researcher"
ROLE_STUDENT = "student"
ROLE_ADMIN = "admin"


@dataclass
class SensorConfig:
    port: str = ""
    baud_rate: int = 115200
    sample_rate_hz: int = 20
    slots: int = 20
    disk_diameter_mm: float = 75.0


@dataclass
class Scenario:
    id: str
    name_ru: str
    name_en: str
    description_ru: str
    description_en: str
    unit: str = UNIT_RAD_S
    interval_ms: int = 500
    sensor: SensorConfig = field(default_factory=SensorConfig)
    has_simulation: bool = False
    allowed_roles: list = field(default_factory=lambda: [ROLE_RESEARCHER, ROLE_STUDENT, ROLE_ADMIN])

    def name(self, lang: str = "ru") -> str:
        return self.name_ru if lang == "ru" else self.name_en

    def description(self, lang: str = "ru") -> str:
        return self.description_ru if lang == "ru" else self.description_en


BUILTIN_SCENARIOS: list[Scenario] = [
    Scenario(
        id="qualitative",
        name_ru="Качественный анализ",
        name_en="Qualitative Analysis",
        description_ru="Демонстрация закономерностей: быстрее/медленнее, растёт/убывает.",
        description_en="Demonstrate patterns: faster/slower, increasing/decreasing.",
        unit=UNIT_RAD_S,
        interval_ms=500,
        sensor=SensorConfig(sample_rate_hz=10),
    ),
    Scenario(
        id="quantitative",
        name_ru="Количественный анализ",
        name_en="Quantitative Analysis",
        description_ru="Точные измерения и обработка числовых данных.",
        description_en="Precise measurements and numerical data processing.",
        unit=UNIT_RAD_S,
        interval_ms=100,
        sensor=SensorConfig(sample_rate_hz=100),
    ),
    Scenario(
        id="fluid_simulation",
        name_ru="Жидкость во вращающемся сосуде",
        name_en="Fluid in Rotating Vessel",
        description_ru="Интеграция с модулем моделирования поведения жидкости.",
        description_en="Integration with fluid behaviour simulation module.",
        unit=UNIT_RAD_S,
        interval_ms=100,
        sensor=SensorConfig(sample_rate_hz=50),
        has_simulation=True,
    ),
]


def load_scenarios(scenarios_dir: str) -> list[Scenario]:
    scenarios = list(BUILTIN_SCENARIOS)
    if not os.path.isdir(scenarios_dir):
        return scenarios
    for fname in os.listdir(scenarios_dir):
        if fname.endswith(".scenario"):
            path = os.path.join(scenarios_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sensor_data = data.pop("sensor", {})
                data["sensor"] = SensorConfig(**sensor_data)
                scenarios.append(Scenario(**data))
            except Exception:
                pass
    return scenarios
''',

    "ui/main_window.py": '''\
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QLabel, QComboBox, QTabWidget, QStatusBar, QToolBar,
)
from PySide6.QtCore import Qt

from core.settings import AppSettings
from scenarios.scenarios import Scenario
from ui.scenarios_widget import ScenariosWidget


LANG_OPTIONS = [("Русский", "ru"), ("English", "en")]


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._lang = settings.get("language", "ru")

        self.setWindowTitle("SpeedSensor Lab")
        self.setMinimumSize(900, 620)
        self._apply_stylesheet()
        self._build_ui()

    def _build_ui(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolBar { border: none; padding: 4px 8px; }")

        lbl_lang = QLabel("Язык / Language: ")
        toolbar.addWidget(lbl_lang)

        self._cb_lang = QComboBox()
        for label, code in LANG_OPTIONS:
            self._cb_lang.addItem(label, code)
        idx = self._cb_lang.findData(self._lang)
        if idx >= 0:
            self._cb_lang.setCurrentIndex(idx)
        self._cb_lang.currentIndexChanged.connect(self._on_lang_changed)
        toolbar.addWidget(self._cb_lang)

        self.addToolBar(toolbar)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        self._scenarios_widget = ScenariosWidget(self._settings, self._lang)
        self._scenarios_widget.scenario_launched.connect(self._on_scenario_launched)
        self._tabs.addTab(self._scenarios_widget, "📋  Сценарии")
        self._tabs.addTab(self._make_placeholder("Окно эксперимента"), "📈  Эксперимент")
        self._tabs.addTab(self._make_placeholder("Обработка данных"), "🔬  Обработка")
        self._tabs.addTab(self._make_placeholder("Моделирование жидкости"), "🌊  Моделирование")

        self.setCentralWidget(self._tabs)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Готово" if self._lang == "ru" else "Ready")

    def _make_placeholder(self, text: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        lbl = QLabel(f"[ {text} — в разработке ]")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #888; font-size: 16px;")
        layout.addWidget(lbl)
        return w

    def _on_lang_changed(self, idx: int):
        self._lang = self._cb_lang.itemData(idx)
        self._settings.set("language", self._lang)
        self._scenarios_widget.set_language(self._lang)
        tab_labels_ru = ["📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]
        tab_labels_en = ["📋  Scenarios",  "📈  Experiment",  "🔬  Processing", "🌊  Simulation"]
        labels = tab_labels_ru if self._lang == "ru" else tab_labels_en
        for i, lbl in enumerate(labels):
            self._tabs.setTabText(i, lbl)
        self._status.showMessage("Готово" if self._lang == "ru" else "Ready")

    def _on_scenario_launched(self, scenario: Scenario):
        self._status.showMessage(
            f"Запущен сценарий: {scenario.name(self._lang)} | Порт: {scenario.sensor.port or \'—\'}"
        )
        self._tabs.setCurrentIndex(1)

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: "Segoe UI", "Ubuntu", sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #181825;
                color: #a6adc8;
                padding: 8px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #1e1e2e;
                color: #cba6f7;
                border-bottom: 2px solid #cba6f7;
            }
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 6px;
                color: #a6e3a1;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QListWidget {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #313244;
                color: #cba6f7;
            }
            QListWidget::item:hover:!selected {
                background: #262637;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background: #181825;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
                color: #cdd6f4;
            }
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #cba6f7;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QPushButton {
                background: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 5px 12px;
                color: #cdd6f4;
            }
            QPushButton:hover { background: #45475a; }
            QPushButton[class="primary-btn"] {
                background: #cba6f7;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 20px;
                font-size: 14px;
                border: none;
            }
            QPushButton[class="primary-btn"]:hover { background: #d0b4ff; }
            QPushButton[class="primary-btn"]:disabled {
                background: #45475a;
                color: #6c7086;
            }
            QLabel[class="section-title"] {
                font-size: 14px;
                font-weight: bold;
                color: #89b4fa;
            }
            QLabel[class="scenario-title"] {
                font-size: 16px;
                font-weight: bold;
                color: #cdd6f4;
            }
            QLabel[class="scenario-desc"] { color: #a6adc8; }
            QScrollArea { border: none; }
            QStatusBar {
                background: #181825;
                color: #a6adc8;
                border-top: 1px solid #313244;
            }
            QToolBar {
                background: #181825;
                border-bottom: 1px solid #313244;
            }
        """)
''',

    "ui/scenarios_widget.py": '''\
import copy
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QComboBox, QSpinBox, QGroupBox, QPushButton, QFormLayout,
    QFrame, QScrollArea, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, Signal

from scenarios.scenarios import (
    Scenario, load_scenarios,
    UNIT_RAD_S, UNIT_RPS,
    ROLE_RESEARCHER, ROLE_STUDENT, ROLE_ADMIN,
)
from core.serial_utils import list_serial_ports
from core.settings import AppSettings


ROLE_LABELS = {
    ROLE_RESEARCHER: {"ru": "Исследователь", "en": "Researcher"},
    ROLE_STUDENT:    {"ru": "Студент",        "en": "Student"},
    ROLE_ADMIN:      {"ru": "Администратор",  "en": "Administrator"},
}

UNIT_LABELS = {
    UNIT_RAD_S: "рад/с (rad/s)",
    UNIT_RPS:   "об/с (rps)",
}


class ScenariosWidget(QWidget):
    scenario_launched = Signal(Scenario)

    def __init__(self, settings: AppSettings, lang: str = "ru", parent=None):
        super().__init__(parent)
        self._settings = settings
        self._lang = lang
        self._scenarios: list[Scenario] = []
        self._current: Scenario | None = None

        self._build_ui()
        self._load_scenarios()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)

        lbl_list = QLabel("Сценарии" if self._lang == "ru" else "Scenarios")
        lbl_list.setProperty("class", "section-title")
        left.addWidget(lbl_list)

        self._list = QListWidget()
        self._list.setMinimumWidth(220)
        self._list.setMaximumWidth(260)
        self._list.currentRowChanged.connect(self._on_scenario_selected)
        left.addWidget(self._list)

        root.addLayout(left)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(divider)

        right = QVBoxLayout()
        right.setSpacing(12)

        self._lbl_name = QLabel("")
        self._lbl_name.setProperty("class", "scenario-title")
        self._lbl_name.setWordWrap(True)
        right.addWidget(self._lbl_name)

        self._lbl_desc = QLabel("")
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setProperty("class", "scenario-desc")
        right.addWidget(self._lbl_desc)

        grp_meas = QGroupBox("Настройки измерений" if self._lang == "ru" else "Measurement Settings")
        form_meas = QFormLayout(grp_meas)
        form_meas.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._cb_unit = QComboBox()
        for key, label in UNIT_LABELS.items():
            self._cb_unit.addItem(label, key)
        form_meas.addRow("Единицы:", self._cb_unit)

        self._spin_interval = QSpinBox()
        self._spin_interval.setRange(50, 10000)
        self._spin_interval.setSuffix(" мс")
        self._spin_interval.setSingleStep(50)
        form_meas.addRow("Интервал вывода:", self._spin_interval)

        self._spin_sample_rate = QSpinBox()
        self._spin_sample_rate.setRange(10, 1000)
        self._spin_sample_rate.setSuffix(" Гц")
        form_meas.addRow("Частота дискретизации:", self._spin_sample_rate)

        right.addWidget(grp_meas)

        grp_sensor = QGroupBox("Датчик / Порт" if self._lang == "ru" else "Sensor / Port")
        form_sensor = QFormLayout(grp_sensor)

        port_row = QHBoxLayout()
        self._cb_port = QComboBox()
        self._cb_port.setMinimumWidth(120)
        btn_refresh = QPushButton("⟳")
        btn_refresh.setFixedWidth(32)
        btn_refresh.setToolTip("Обновить список портов")
        btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self._cb_port)
        port_row.addWidget(btn_refresh)
        form_sensor.addRow("COM-порт:", port_row)

        self._cb_baud = QComboBox()
        for baud in [9600, 19200, 38400, 57600, 115200, 230400]:
            self._cb_baud.addItem(str(baud), baud)
        self._cb_baud.setCurrentIndex(4)
        form_sensor.addRow("Скорость (baud):", self._cb_baud)

        self._spin_slots = QSpinBox()
        self._spin_slots.setRange(1, 360)
        form_sensor.addRow("Прорезей на диске:", self._spin_slots)

        self._spin_diameter = QDoubleSpinBox()
        self._spin_diameter.setRange(1.0, 500.0)
        self._spin_diameter.setSuffix(" мм")
        self._spin_diameter.setDecimals(1)
        form_sensor.addRow("Диаметр диска:", self._spin_diameter)

        right.addWidget(grp_sensor)

        grp_role = QGroupBox("Роль пользователя" if self._lang == "ru" else "User Role")
        form_role = QFormLayout(grp_role)
        self._cb_role = QComboBox()
        for role, labels in ROLE_LABELS.items():
            self._cb_role.addItem(labels[self._lang], role)
        saved_role = self._settings.get("role", ROLE_RESEARCHER)
        idx = self._cb_role.findData(saved_role)
        if idx >= 0:
            self._cb_role.setCurrentIndex(idx)
        form_role.addRow("Роль:", self._cb_role)
        right.addWidget(grp_role)

        right.addStretch()

        self._btn_launch = QPushButton("▶  Запустить сценарий" if self._lang == "ru" else "▶  Launch Scenario")
        self._btn_launch.setProperty("class", "primary-btn")
        self._btn_launch.setEnabled(False)
        self._btn_launch.clicked.connect(self._on_launch)
        right.addWidget(self._btn_launch)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setLayout(right)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        self._refresh_ports()

    def _load_scenarios(self):
        self._scenarios = load_scenarios("scenarios")
        self._list.clear()
        for sc in self._scenarios:
            item = QListWidgetItem(sc.name(self._lang))
            item.setData(Qt.ItemDataRole.UserRole, sc)
            self._list.addItem(item)
        if self._scenarios:
            self._list.setCurrentRow(0)

    def _refresh_ports(self):
        self._cb_port.clear()
        ports = list_serial_ports()
        for p in ports:
            self._cb_port.addItem(p)
        saved = self._settings.get("last_port", "")
        idx = self._cb_port.findText(saved)
        if idx >= 0:
            self._cb_port.setCurrentIndex(idx)

    def _on_scenario_selected(self, row: int):
        if row < 0 or row >= len(self._scenarios):
            return
        sc = self._scenarios[row]
        self._current = sc
        self._lbl_name.setText(sc.name(self._lang))
        self._lbl_desc.setText(sc.description(self._lang))

        unit_idx = self._cb_unit.findData(sc.unit)
        if unit_idx >= 0:
            self._cb_unit.setCurrentIndex(unit_idx)
        self._spin_interval.setValue(sc.interval_ms)
        self._spin_sample_rate.setValue(sc.sensor.sample_rate_hz)
        self._spin_slots.setValue(sc.sensor.slots)
        self._spin_diameter.setValue(sc.sensor.disk_diameter_mm)

        baud_idx = self._cb_baud.findData(sc.sensor.baud_rate)
        if baud_idx >= 0:
            self._cb_baud.setCurrentIndex(baud_idx)

        self._btn_launch.setEnabled(True)

    def _on_launch(self):
        if self._current is None:
            return
        sc = copy.deepcopy(self._current)
        sc.unit = self._cb_unit.currentData()
        sc.interval_ms = self._spin_interval.value()
        sc.sensor.sample_rate_hz = self._spin_sample_rate.value()
        sc.sensor.slots = self._spin_slots.value()
        sc.sensor.disk_diameter_mm = self._spin_diameter.value()
        sc.sensor.port = self._cb_port.currentText()
        sc.sensor.baud_rate = self._cb_baud.currentData()

        self._settings.set("last_port", sc.sensor.port)
        self._settings.set("last_unit", sc.unit)
        self._settings.set("role", self._cb_role.currentData())

        self.scenario_launched.emit(sc)

    def set_language(self, lang: str):
        self._lang = lang
        self._load_scenarios()
''',
}


def main():
    base = os.path.dirname(os.path.abspath(__file__))

    for d in DIRS:
        path = os.path.join(base, d)
        os.makedirs(path, exist_ok=True)
        print(f"  DIR  {d}")

    for rel_path, content in FILES.items():
        full_path = os.path.join(base, rel_path)
        if os.path.exists(full_path):
            print(f"  SKIP {rel_path}  (уже существует)")
            continue
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  FILE {rel_path}")

    print("\nГотово. Запуск:")
    print("  pip install -r requirements.txt")
    print("  python main.py")


if __name__ == "__main__":
    main()
