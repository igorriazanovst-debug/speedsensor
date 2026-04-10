"""
Индикатор состояния подключения датчика.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush


class _LedWidget(QWidget):
    """Простой светодиод — круг с цветом."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#45475a")
        self.setFixedSize(14, 14)

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(self._color))
        p.setPen(QPen(self._color.darker(150), 1))
        p.drawEllipse(1, 1, 12, 12)


class ConnectionStatusBar(QWidget):
    """
    Строка состояния подключения.
    Показывает: индикатор | текст статуса | порт | кнопка переподключения
    """
    reconnect_requested = Signal(str)   # device name

    STATUS_SEARCHING   = "searching"
    STATUS_CONNECTED   = "connected"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_ERROR       = "error"

    _COLORS = {
        STATUS_SEARCHING:    "#f9e2af",   # жёлтый
        STATUS_CONNECTED:    "#a6e3a1",   # зелёный
        STATUS_DISCONNECTED: "#f38ba8",   # красный
        STATUS_ERROR:        "#fab387",   # оранжевый
    }

    _TEXTS = {
        STATUS_SEARCHING:    "Поиск датчика...",
        STATUS_CONNECTED:    "Датчик подключён",
        STATUS_DISCONNECTED: "Датчик не найден",
        STATUS_ERROR:        "Ошибка подключения",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = self.STATUS_DISCONNECTED
        self._build_ui()

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        self._led = _LedWidget()
        lay.addWidget(self._led)

        self._lbl_status = QLabel("Датчик не найден")
        self._lbl_status.setStyleSheet("font-weight: bold;")
        lay.addWidget(self._lbl_status)

        self._lbl_port = QLabel("")
        self._lbl_port.setStyleSheet("color: #a6adc8; font-size: 11px;")
        lay.addWidget(self._lbl_port)

        lay.addStretch()

        self._btn_reconnect = QPushButton("⟳ Найти датчик")
        self._btn_reconnect.setFixedHeight(26)
        self._btn_reconnect.clicked.connect(self._on_reconnect)
        lay.addWidget(self._btn_reconnect)

        self.setStyleSheet("""
            ConnectionStatusBar {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 6px;
            }
        """)
        self._apply_status()

    # ----------------------------------------------------------------- API --

    def set_status(self, status: str, port: str = "", extra: str = ""):
        self._status = status
        self._port = port
        self._apply_status(extra)

    def _apply_status(self, extra: str = ""):
        color = self._COLORS.get(self._status, "#45475a")
        text  = self._TEXTS.get(self._status, "")
        if extra:
            text = f"{text} — {extra}"

        self._led.set_color(color)
        self._lbl_status.setText(text)
        self._lbl_status.setStyleSheet(f"font-weight: bold; color: {color};")

        port = getattr(self, "_port", "")
        self._lbl_port.setText(f"({port})" if port else "")

        is_searching = self._status == self.STATUS_SEARCHING
        self._btn_reconnect.setEnabled(not is_searching)

    def _on_reconnect(self):
        self.reconnect_requested.emit(getattr(self, "_port", ""))
