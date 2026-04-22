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
