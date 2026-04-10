"""
Экран выбора режима работы:
  ┌─────────────────────────────────┐
  │  [🔌 Реальный датчик]           │
  │  [🧪 Моделирование эксперимента]│
  └─────────────────────────────────┘
Показывается вместо вкладки эксперимента до тех пор,
пока пользователь не сделал выбор.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


MODE_SENSOR     = "sensor"
MODE_SIMULATION = "simulation"


class ModeCard(QFrame):
    """Карточка выбора режима."""
    clicked = Signal()

    def __init__(self, icon: str, title: str, subtitle: str,
                 accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(300, 200)
        self._build(icon, title, subtitle, accent)

    def _build(self, icon, title, subtitle, accent):
        self.setStyleSheet(f"""
            ModeCard {{
                background: #181825;
                border: 2px solid #313244;
                border-radius: 16px;
            }}
            ModeCard:hover {{
                border: 2px solid {accent};
                background: #1e1e2e;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_icon = QLabel(icon)
        lbl_icon.setFont(QFont("Segoe UI Emoji", 42))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(lbl_icon)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(f"color: {accent}; background: transparent; border: none;")
        lay.addWidget(lbl_title)

        lbl_sub = QLabel(subtitle)
        lbl_sub.setFont(QFont("Segoe UI", 10))
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet("color: #a6adc8; background: transparent; border: none;")
        lay.addWidget(lbl_sub)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ModeSelectorWidget(QWidget):
    """
    Экран выбора режима.
    Эмитирует mode_selected(MODE_SENSOR | MODE_SIMULATION).
    """
    mode_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Заголовок
        lbl_title = QLabel("Выберите режим работы")
        lbl_title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("color: #cdd6f4; margin-bottom: 8px;")
        root.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Работа с реальным датчиком или моделирование эксперимента без оборудования"
        )
        lbl_sub.setFont(QFont("Segoe UI", 11))
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("color: #6c7086; margin-bottom: 40px;")
        lbl_sub.setWordWrap(True)
        root.addWidget(lbl_sub)

        # Карточки
        cards_row = QHBoxLayout()
        cards_row.setSpacing(32)
        cards_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._card_sensor = ModeCard(
            icon="🔌",
            title="Реальный датчик",
            subtitle="Подключение к nRF52840\nчерез USB Serial",
            accent="#89b4fa",
        )
        self._card_sensor.clicked.connect(
            lambda: self.mode_selected.emit(MODE_SENSOR)
        )
        cards_row.addWidget(self._card_sensor)

        self._card_sim = ModeCard(
            icon="🧪",
            title="Моделирование",
            subtitle="Симуляция эксперимента\nбез оборудования",
            accent="#a6e3a1",
        )
        self._card_sim.clicked.connect(
            lambda: self.mode_selected.emit(MODE_SIMULATION)
        )
        cards_row.addWidget(self._card_sim)

        root.addLayout(cards_row)
