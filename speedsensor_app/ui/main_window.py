"""
Главное окно.

Поток экранов (QStackedWidget):
  [0] ScenariosWidget      — выбор сценария
  [1] ModeSelectorWidget   — выбор режима (датчик / симуляция)
  [2] SensorConnectWidget  — подключение датчика (только для реального режима)
  [3] ExperimentWidget     — сам эксперимент

Переходы:
  Сценарии → выбор режима             (кнопка «Запустить сценарий»)
  Выбор режима → подключение датчика  (выбор «Реальный датчик»)
  Выбор режима → эксперимент          (выбор «Моделирование»)
  Подключение датчика → эксперимент   (успешное подключение)
  Эксперимент → выбор режима          (кнопка «Сменить режим»)
  Любой → сценарии                    (вкладки наверху)
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QLabel, QComboBox, QTabWidget, QStatusBar,
    QToolBar, QStackedWidget,
)
from PySide6.QtCore import Qt

from core.settings import AppSettings
from scenarios.scenarios import Scenario
from ui.scenarios_widget import ScenariosWidget
from ui.mode_selector import ModeSelectorWidget, MODE_SENSOR, MODE_SIMULATION
from ui.sensor_connect_widget import SensorConnectWidget
from ui.experiment_widget import ExperimentWidget

LANG_OPTIONS = [("Русский", "ru"), ("English", "en")]

IDX_SCENARIOS = 0
IDX_MODE      = 1
IDX_CONNECT   = 2
IDX_EXPERIMENT = 3


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._lang = settings.get("language", "ru")
        self._current_scenario: Scenario | None = None

        self.setWindowTitle("SpeedSensor Lab")
        self.setMinimumSize(960, 640)
        self._apply_stylesheet()
        self._build_ui()

    # ================================================================= UI ==

    def _build_ui(self):
        # ── Toolbar ──────────────────────────────────────────────────────
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolBar { border: none; padding: 4px 8px; }")
        toolbar.addWidget(QLabel("Язык / Language: "))

        self._cb_lang = QComboBox()
        for label, code in LANG_OPTIONS:
            self._cb_lang.addItem(label, code)
        idx = self._cb_lang.findData(self._lang)
        if idx >= 0:
            self._cb_lang.setCurrentIndex(idx)
        self._cb_lang.currentIndexChanged.connect(self._on_lang_changed)
        toolbar.addWidget(self._cb_lang)
        self.addToolBar(toolbar)

        # ── Tabs (верхние вкладки только для навигации) ───────────────────
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Вкладка «Сценарии» — содержит QStackedWidget для экранов эксперимента
        scenarios_outer = QWidget()
        outer_lay = QVBoxLayout(scenarios_outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)

        # Stacked: сценарии
        self._stack_scenarios = QStackedWidget()
        self._scenarios_widget = ScenariosWidget(self._settings, self._lang)
        self._scenarios_widget.scenario_launched.connect(self._on_scenario_launched)
        self._stack_scenarios.addWidget(self._scenarios_widget)   # idx 0
        outer_lay.addWidget(self._stack_scenarios)
        self._tabs.addTab(scenarios_outer, "📋  Сценарии")

        # Вкладка «Эксперимент» — содержит QStackedWidget для всего потока
        experiment_outer = QWidget()
        exp_outer_lay = QVBoxLayout(experiment_outer)
        exp_outer_lay.setContentsMargins(0, 0, 0, 0)

        self._stack_exp = QStackedWidget()

        # Экраны потока эксперимента
        self._mode_selector = ModeSelectorWidget()
        self._mode_selector.mode_selected.connect(self._on_mode_selected)
        self._stack_exp.addWidget(self._mode_selector)            # IDX_MODE=0

        self._sensor_connect = SensorConnectWidget()
        self._sensor_connect.connected.connect(self._on_sensor_connected)
        self._sensor_connect.back_requested.connect(self._on_back_to_mode)
        self._stack_exp.addWidget(self._sensor_connect)           # IDX_CONNECT=1

        self._experiment = ExperimentWidget()
        self._experiment.back_requested.connect(self._on_back_to_mode)
        self._stack_exp.addWidget(self._experiment)               # IDX_EXPERIMENT=2

        self._stack_exp.setCurrentIndex(0)
        exp_outer_lay.addWidget(self._stack_exp)
        self._tabs.addTab(experiment_outer, "📈  Эксперимент")

        # Остальные вкладки-заглушки
        self._tabs.addTab(self._make_placeholder("Обработка данных"), "🔬  Обработка")
        self._tabs.addTab(self._make_placeholder("Моделирование жидкости"), "🌊  Моделирование")

        self.setCentralWidget(self._tabs)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Готово")

    def _make_placeholder(self, text: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(f"[ {text} — в разработке ]")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #888; font-size: 16px;")
        lay.addWidget(lbl)
        return w

    # ========================================================== navigation ==

    def _on_scenario_launched(self, scenario: Scenario):
        self._current_scenario = scenario
        self._stack_exp.setCurrentIndex(0)   # показать выбор режима
        self._tabs.setCurrentIndex(1)         # переключить на вкладку эксперимента
        self._status.showMessage(f"Сценарий: {scenario.name(self._lang)}")

    def _on_mode_selected(self, mode: str):
        if mode == MODE_SIMULATION:
            self._experiment.setup(
                mode=MODE_SIMULATION,
                scenario=self._current_scenario,
            )
            self._stack_exp.setCurrentIndex(2)   # → эксперимент
        else:
            # Перезапустить сканер при каждом входе
            self._sensor_connect._scanner.start()
            self._sensor_connect._set_state_searching()
            self._stack_exp.setCurrentIndex(1)   # → подключение датчика

    def _on_sensor_connected(self, port: str, baud: int):
        self._experiment.setup(
            mode=MODE_SENSOR,
            port=port,
            baud=baud,
            scenario=self._current_scenario,
        )
        self._stack_exp.setCurrentIndex(2)   # → эксперимент

    def _on_back_to_mode(self):
        self._stack_exp.setCurrentIndex(0)   # → выбор режима

    def _on_tab_changed(self, idx: int):
        # При возврате на вкладку «Сценарии» — ничего лишнего не делаем
        pass

    def _on_lang_changed(self, idx: int):
        self._lang = self._cb_lang.itemData(idx)
        self._settings.set("language", self._lang)
        self._scenarios_widget.set_language(self._lang)
        tab_ru = ["📋  Сценарии", "📈  Эксперимент", "🔬  Обработка", "🌊  Моделирование"]
        tab_en = ["📋  Scenarios", "📈  Experiment",  "🔬  Processing", "🌊  Simulation"]
        for i, lbl in enumerate(tab_ru if self._lang == "ru" else tab_en):
            self._tabs.setTabText(i, lbl)

    # ========================================================= stylesheet ==

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: "Segoe UI", "Ubuntu", sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane { border: 1px solid #313244; border-radius: 6px; }
            QTabBar::tab {
                background: #181825; color: #a6adc8;
                padding: 8px 18px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #1e1e2e; color: #cba6f7;
                border-bottom: 2px solid #cba6f7;
            }
            QGroupBox {
                border: 1px solid #313244; border-radius: 6px;
                margin-top: 10px; padding-top: 6px;
                color: #a6e3a1; font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QListWidget {
                background: #181825; border: 1px solid #313244; border-radius: 6px;
            }
            QListWidget::item { padding: 8px 10px; border-radius: 4px; }
            QListWidget::item:selected { background: #313244; color: #cba6f7; }
            QListWidget::item:hover:!selected { background: #262637; }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background: #181825; border: 1px solid #45475a;
                border-radius: 4px; padding: 4px 8px; color: #cdd6f4;
            }
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #cba6f7;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QSlider::groove:horizontal {
                height: 4px; background: #45475a; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #cba6f7; width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #cba6f7; border-radius: 2px; }
            QPushButton {
                background: #313244; border: 1px solid #45475a;
                border-radius: 4px; padding: 5px 12px; color: #cdd6f4;
            }
            QPushButton:hover { background: #45475a; }
            QPushButton[class="primary-btn"] {
                background: #cba6f7; color: #1e1e2e;
                font-weight: bold; padding: 8px 20px; font-size: 14px; border: none;
            }
            QPushButton[class="primary-btn"]:hover { background: #d0b4ff; }
            QPushButton[class="primary-btn"]:disabled { background: #45475a; color: #6c7086; }
            QLabel[class="section-title"] {
                font-size: 14px; font-weight: bold; color: #89b4fa;
            }
            QLabel[class="scenario-title"] {
                font-size: 16px; font-weight: bold; color: #cdd6f4;
            }
            QLabel[class="scenario-desc"] { color: #a6adc8; }
            QScrollArea { border: none; }
            QStatusBar {
                background: #181825; color: #a6adc8;
                border-top: 1px solid #313244;
            }
            QToolBar { background: #181825; border-bottom: 1px solid #313244; }
            QCheckBox { spacing: 6px; }
            QCheckBox::indicator {
                width: 16px; height: 16px;
                border: 1px solid #45475a; border-radius: 3px;
                background: #181825;
            }
            QCheckBox::indicator:checked {
                background: #cba6f7; border-color: #cba6f7;
            }
        """)
