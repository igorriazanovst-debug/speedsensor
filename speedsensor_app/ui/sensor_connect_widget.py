"""
Экран подключения датчика.
Показывается после выбора режима «Реальный датчик».
Состояния:
  SEARCHING  → ищем порты, пробуем probe
  FOUND      → нашли кандидата, ждём подтверждения
  CONNECTED  → probe успешен, кнопка «Начать эксперимент» активна
  ERROR      → ошибка
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush

from core.port_scanner import PortScanner, PortInfo


class _PulsingDot(QWidget):
    """Анимированный индикатор — пульсирующий круг."""

    def __init__(self, color: str = "#f9e2af", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._radius = 8
        self._alpha = 255
        self.setFixedSize(32, 32)

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._step = 0

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def _tick(self):
        import math
        self._step = (self._step + 1) % 40
        self._alpha = int(128 + 127 * math.sin(self._step / 40 * 2 * 3.14159))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._color)
        c.setAlpha(self._alpha)
        p.setBrush(QBrush(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(8, 8, 16, 16)


class SensorConnectWidget(QWidget):
    """
    Экран подключения датчика.
    Эмитирует:
        connected(port: str, baud: int)  — успешное подключение, готово к старту
        back_requested()                 — пользователь хочет вернуться к выбору режима
    """
    connected     = Signal(str, int)   # (port, baud)
    back_requested = Signal()

    def __init__(self, scanner: "PortScanner | None" = None, parent=None):
        super().__init__(parent)
        self._confirmed_port: PortInfo | None = None
        self._scanner_is_shared = scanner is not None

        self._scanner = scanner if scanner is not None else PortScanner(self)
        self._scanner.ports_updated.connect(self._on_ports_updated)
        self._scanner.sensor_found.connect(self._on_sensor_found)
        self._scanner.sensor_lost.connect(self._on_sensor_lost)

        self._build_ui()
        self._set_state_searching()
        if not self._scanner_is_shared:
            self._scanner.start()

    # ================================================================= UI ==

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setSpacing(0)

        # Кнопка «Назад»
        back_row = QHBoxLayout()
        back_row.setContentsMargins(16, 12, 16, 0)
        self._btn_back = QPushButton("← Назад")
        self._btn_back.setFixedWidth(90)
        self._btn_back.setFixedHeight(28)
        self._btn_back.clicked.connect(self._on_back)
        back_row.addWidget(self._btn_back)
        back_row.addStretch()
        root.addLayout(back_row)

        root.addStretch()

        # Центральная карточка
        card = QFrame()
        card.setFixedWidth(480)
        card.setStyleSheet("""
            QFrame {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 16px;
            }
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(40, 36, 40, 36)
        card_lay.setSpacing(16)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Иконка + пульс
        dot_row = QHBoxLayout()
        dot_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dot = _PulsingDot("#f9e2af")
        self._dot.start()
        dot_row.addWidget(self._dot)
        card_lay.addLayout(dot_row)

        # Заголовок
        self._lbl_title = QLabel("Поиск датчика...")
        self._lbl_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_title.setStyleSheet("color: #cdd6f4;")
        card_lay.addWidget(self._lbl_title)

        # Подзаголовок
        self._lbl_sub = QLabel(
            "Подключите датчик через USB и подождите\nили выберите порт вручную"
        )
        self._lbl_sub.setFont(QFont("Segoe UI", 10))
        self._lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_sub.setWordWrap(True)
        self._lbl_sub.setStyleSheet("color: #6c7086;")
        card_lay.addWidget(self._lbl_sub)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: 1px solid #313244;")
        card_lay.addWidget(sep)

        # Выбор порта
        port_row = QHBoxLayout()
        port_row.setSpacing(8)
        lbl_port = QLabel("Порт:")
        lbl_port.setStyleSheet("color: #a6adc8;")
        lbl_port.setFixedWidth(40)
        port_row.addWidget(lbl_port)

        self._cb_port = QComboBox()
        self._cb_port.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        port_row.addWidget(self._cb_port, 1)

        btn_rescan = QPushButton("⟳")
        btn_rescan.setFixedWidth(34)
        btn_rescan.setFixedHeight(30)
        btn_rescan.setToolTip("Обновить список портов")
        btn_rescan.clicked.connect(self._scanner._scan)
        port_row.addWidget(btn_rescan)
        card_lay.addLayout(port_row)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._btn_connect = QPushButton("🔌  Подключить")
        self._btn_connect.setFixedHeight(38)
        self._btn_connect.setProperty("class", "primary-btn")
        self._btn_connect.clicked.connect(self._on_manual_connect)
        btn_row.addWidget(self._btn_connect)

        self._btn_start = QPushButton("▶  Начать эксперимент")
        self._btn_start.setFixedHeight(38)
        self._btn_start.setProperty("class", "primary-btn")
        self._btn_start.setEnabled(False)
        self._btn_start.setVisible(False)
        self._btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self._btn_start)

        card_lay.addLayout(btn_row)

        root.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        root.addStretch()

    # ============================================================== states ==

    def _set_state_searching(self):
        self._dot.set_color("#f9e2af")
        self._dot.start()
        self._lbl_title.setText("Поиск датчика...")
        self._lbl_title.setStyleSheet("color: #cdd6f4;")
        self._lbl_sub.setText(
            "Подключите датчик через USB и подождите\nили выберите порт вручную"
        )
        self._btn_connect.setVisible(True)
        self._btn_start.setVisible(False)
        self._btn_start.setEnabled(False)

    def _set_state_connected(self, info: PortInfo):
        self._dot.set_color("#a6e3a1")
        self._dot.stop()
        self._lbl_title.setText("Датчик подключён")
        self._lbl_title.setStyleSheet("color: #a6e3a1;")
        self._lbl_sub.setText(
            f"Порт: {info.device}\n{info.description}"
        )
        self._btn_connect.setVisible(False)
        self._btn_start.setVisible(True)
        self._btn_start.setEnabled(True)

    def _set_state_lost(self):
        self._confirmed_port = None
        self._dot.set_color("#f38ba8")
        self._dot.start()
        self._lbl_title.setText("Датчик отключён")
        self._lbl_title.setStyleSheet("color: #f38ba8;")
        self._lbl_sub.setText("Датчик был отключён. Подключите снова.")
        self._btn_connect.setVisible(True)
        self._btn_start.setVisible(False)
        self._btn_start.setEnabled(False)

    def _set_state_error(self, msg: str):
        self._dot.set_color("#fab387")
        self._dot.stop()
        self._lbl_title.setText("Ошибка подключения")
        self._lbl_title.setStyleSheet("color: #fab387;")
        self._lbl_sub.setText(msg)
        self._btn_connect.setVisible(True)
        self._btn_start.setVisible(False)

    # ============================================================= scanner ==

    def _on_ports_updated(self, ports: list):
        current = self._cb_port.currentData()
        self._cb_port.clear()
        for p in ports:
            self._cb_port.addItem(f"{p.device}  —  {p.description}", p.device)
        # Восстановить выбранный
        if current:
            idx = self._cb_port.findData(current)
            if idx >= 0:
                self._cb_port.setCurrentIndex(idx)

    def _on_sensor_found(self, info: PortInfo):
        self._confirmed_port = info
        # Выбрать в комбобоксе
        for i in range(self._cb_port.count()):
            if self._cb_port.itemData(i) == info.device:
                self._cb_port.setCurrentIndex(i)
                break
        self._set_state_connected(info)

    def _on_sensor_lost(self):
        self._set_state_lost()

    # ============================================================= actions ==

    def _on_manual_connect(self):
        """Ручное подключение — probe выбранного порта."""
        port = self._cb_port.currentData()
        if not port:
            self._set_state_error("Выберите порт из списка")
            return
        self._lbl_title.setText("Проверка порта...")
        self._lbl_sub.setText(f"Подключаемся к {port}...")
        self._dot.set_color("#f9e2af")
        self._dot.start()
        self._btn_connect.setEnabled(False)

        # Запускаем probe в фоне
        from core.port_scanner import _probe_port
        import threading

        def do_probe():
            result = _probe_port(port)
            if result is not None:
                self._confirmed_port = result
                self._on_sensor_found(result)
            else:
                self._set_state_error(
                    f"Порт {port} не отвечает.\n"
                    "Проверьте прошивку и скорость соединения."
                )
            self._btn_connect.setEnabled(True)

        threading.Thread(target=do_probe, daemon=True).start()

    def _on_start(self):
        if self._confirmed_port:
            if not self._scanner_is_shared:
                self._scanner.stop()
            self.connected.emit(self._confirmed_port.device, 115200)

    def sync_state(self):
        """Синхронизировать UI с текущим состоянием shared scanner.
        Вызывается из MainWindow при каждом показе этого экрана."""
        confirmed = self._scanner.confirmed_port
        if confirmed:
            self._confirmed_port = confirmed
            # Убедиться что порт есть в комбобоксе
            found = False
            for i in range(self._cb_port.count()):
                if self._cb_port.itemData(i) == confirmed.device:
                    self._cb_port.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                self._cb_port.addItem(
                    f"{confirmed.device}  —  {confirmed.description or 'датчик'}",
                    confirmed.device,
                )
                self._cb_port.setCurrentIndex(self._cb_port.count() - 1)
            self._set_state_connected(confirmed)
        else:
            self._confirmed_port = None
            self._set_state_searching()
            # Принудительно обновить список портов из последнего скана
            self._scanner._scan()

    def _on_back(self):
        if not self._scanner_is_shared:
            self._scanner.stop()
        self.back_requested.emit()
