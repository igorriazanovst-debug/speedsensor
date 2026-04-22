"""
Стартовая вкладка «Цифровой лабораторный комплекс «Познайкино-НЕО»».

Изображение (assets/logo.png) занимает всю площадь вкладки.
Поверх — полупрозрачная панель с заголовком и карточками датчиков.
"""
from __future__ import annotations
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QBrush

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

_LOGO_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")
)

CARD_STYLE = """
QFrame#sensor-card {
    background: rgba(24, 24, 37, 210);
    border: 1px solid #45475a;
    border-radius: 10px;
}
"""

OVERLAY_STYLE = """
QWidget#overlay-panel {
    background: transparent;
}
"""


def _build_scenario_map(scenarios_dir: str) -> dict[str, tuple[int, str]]:
    try:
        scenarios = load_scenarios(scenarios_dir)
    except Exception:
        scenarios = []
    return {sc.id: (i + 1, sc.name_ru) for i, sc in enumerate(scenarios)}


# ─── Карточка датчика ─────────────────────────────────────────────────────────

class SensorCard(QFrame):
    def __init__(
        self,
        port_info: PortInfo,
        scenario_map: dict[str, tuple[int, str]],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("sensor-card")
        self.setFixedWidth(300)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(CARD_STYLE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(5)

        serial_lbl = QLabel(f"🔌  {port_info.device}")
        serial_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {C_GREEN};"
            " background: transparent;"
        )
        lay.addWidget(serial_lbl)

        if port_info.sensor_serial:
            sn_lbl = QLabel(f"№  {port_info.sensor_serial}")
            sn_lbl.setStyleSheet(
                f"font-size: 12px; color: {C_SUBTEXT}; background: transparent;"
            )
            lay.addWidget(sn_lbl)

        name = port_info.sensor_name or "Датчик угловой скорости"
        name_lbl = QLabel(name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            f"font-size: 13px; color: {C_TEXT}; background: transparent;"
        )
        lay.addWidget(name_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C_BORDER}; background: transparent;")
        lay.addWidget(sep)

        hdr = QLabel("Сценарии экспериментов:")
        hdr.setStyleSheet(
            f"font-size: 11px; color: {C_SUBTEXT}; background: transparent;"
        )
        lay.addWidget(hdr)

        raw = port_info.sensor_scenarios
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
                lbl.setStyleSheet(
                    f"font-size: 11px; color: {C_TEXT}; background: transparent;"
                )
                lay.addWidget(lbl)
        else:
            no_sc = QLabel("  —")
            no_sc.setStyleSheet(
                f"font-size: 11px; color: {C_SUBTEXT}; background: transparent;"
            )
            lay.addWidget(no_sc)

        lay.addStretch()


# ─── Overlay-панель (заголовок + карточки) ────────────────────────────────────

class _OverlayPanel(QWidget):
    """Полупрозрачная панель поверх фонового изображения."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("overlay-panel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(OVERLAY_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 32)
        root.setSpacing(12)

        # Заголовок
        self._title = QLabel("Цифровой лабораторный комплекс «Познайкино-НЕО»")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setWordWrap(True)
        self._title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._title.setStyleSheet(
            f"color: {C_ACCENT};"
            " background: rgba(30,30,46,180);"
            " border-radius: 8px;"
            " padding: 10px 20px;"
        )
        root.addWidget(self._title)

        root.addStretch()

        # Секция карточек — прижата к низу
        self._sec_lbl = QLabel("Подключённые датчики")
        self._sec_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {C_BLUE};"
            " background: transparent;"
        )
        root.addWidget(self._sec_lbl)

        self._cards_row = QHBoxLayout()
        self._cards_row.setContentsMargins(0, 0, 0, 0)
        self._cards_row.setSpacing(16)
        self._cards_row.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        root.addLayout(self._cards_row)

        self._no_sensors_lbl = QLabel(
            "Датчики не обнаружены. Подключите датчик к USB."
        )
        self._no_sensors_lbl.setStyleSheet(
            f"font-size: 13px; color: {C_SUBTEXT}; background: transparent;"
        )
        root.addWidget(self._no_sensors_lbl)

    def refresh_cards(
        self,
        ports: list[PortInfo],
        scenario_map: dict[str, tuple[int, str]],
    ):
        while self._cards_row.count():
            item = self._cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if ports:
            self._no_sensors_lbl.hide()
            self._sec_lbl.show()
            for pi in ports:
                self._cards_row.addWidget(SensorCard(pi, scenario_map))
            self._cards_row.addStretch()
        else:
            self._sec_lbl.hide()
            self._no_sensors_lbl.show()


# ─── Главный виджет ───────────────────────────────────────────────────────────

class HomeWidget(QWidget):
    """Стартовая вкладка: фоновое изображение + overlay с карточками."""

    def __init__(self, scanner: PortScanner, scenarios_dir: str = "", parent=None):
        super().__init__(parent)
        self._scanner = scanner
        self._scenarios_dir = scenarios_dir
        self._scenario_map: dict[str, tuple[int, str]] = {}
        self._pixmap = QPixmap(_LOGO_PATH) if os.path.isfile(_LOGO_PATH) else QPixmap()

        self._build_ui()
        self._reload_scenario_map()

        self._scanner.sensor_found.connect(self._on_update)
        self._scanner.sensor_lost.connect(self._on_update)
        self._scanner.ports_updated.connect(self._on_update)

    def _reload_scenario_map(self):
        self._scenario_map = _build_scenario_map(self._scenarios_dir)

    def _build_ui(self):
        # Overlay поверх self — будет растянут в resizeEvent
        self._overlay = _OverlayPanel(self)
        self._overlay.setGeometry(self.rect())
        self._refresh_cards()

    def resizeEvent(self, event):
        self._overlay.setGeometry(self.rect())
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width()  - scaled.width())  // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            p.fillRect(self.rect(), QColor(C_BG))
            p.setPen(QColor(C_BORDER))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "[ Изображение: assets/logo.png ]",
            )

    @Slot()
    def _on_update(self, *args):
        self._refresh_cards()

    def _refresh_cards(self):
        confirmed = self._scanner.confirmed_port
        ports: list[PortInfo] = [confirmed] if confirmed else []
        self._overlay.refresh_cards(ports, self._scenario_map)
