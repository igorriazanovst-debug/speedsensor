from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QComboBox, QSpinBox, QGroupBox, QPushButton, QFormLayout,
    QFrame, QSizePolicy, QScrollArea, QCheckBox, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

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

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ── Left: scenario list ──────────────────────────────────────────
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

        # ── Divider ──────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(divider)

        # ── Right: details + settings ────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(12)

        # Description
        self._lbl_name = QLabel("")
        self._lbl_name.setProperty("class", "scenario-title")
        self._lbl_name.setWordWrap(True)
        right.addWidget(self._lbl_name)

        self._lbl_desc = QLabel("")
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setProperty("class", "scenario-desc")
        right.addWidget(self._lbl_desc)

        # ── Settings group ───────────────────────────────────────────────
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

        # ── Sensor group ─────────────────────────────────────────────────
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
        self._cb_baud.setCurrentIndex(4)  # 115200
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

        # ── Role ─────────────────────────────────────────────────────────
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

        # ── Launch button ────────────────────────────────────────────────
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

    # ---------------------------------------------------------------- logic --

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

        # Populate fields from scenario defaults
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
        # Apply edited settings back to scenario copy
        import copy
        sc = copy.deepcopy(self._current)
        sc.unit = self._cb_unit.currentData()
        sc.interval_ms = self._spin_interval.value()
        sc.sensor.sample_rate_hz = self._spin_sample_rate.value()
        sc.sensor.slots = self._spin_slots.value()
        sc.sensor.disk_diameter_mm = self._spin_diameter.value()
        sc.sensor.port = self._cb_port.currentText()
        sc.sensor.baud_rate = self._cb_baud.currentData()

        # Persist last used settings
        self._settings.set("last_port", sc.sensor.port)
        self._settings.set("last_unit", sc.unit)
        self._settings.set("role", self._cb_role.currentData())

        self.scenario_launched.emit(sc)

    def set_language(self, lang: str):
        self._lang = lang
        self._load_scenarios()
