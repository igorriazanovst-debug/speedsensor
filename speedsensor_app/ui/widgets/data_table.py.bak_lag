"""
Таблица данных с заполнением в реальном времени и экспортом.
"""
import os
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFileDialog, QAbstractItemView, QHeaderView,
    QMessageBox, QComboBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

from core.experiment_data import ExperimentData


_HEADER_COLOR = QColor("#313244")
_ROW_ODD      = QColor("#1e1e2e")
_ROW_EVEN     = QColor("#181825")
_TEXT_COLOR   = QColor("#cdd6f4")
_ACCENT       = QColor("#cba6f7")

MAX_DISPLAY_ROWS = 5000   # ограничение таблицы в UI (данные хранятся все)


class DataTableWidget(QWidget):
    def __init__(self, data: ExperimentData, parent=None):
        super().__init__(parent)
        self._data = data
        self._displayed_rows = 0

        # Буферизация: обновляем таблицу не чаще 10 раз/с
        self._pending = False
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(100)
        self._flush_timer.timeout.connect(self._flush)

        self._build_ui()
        self._flush_timer.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # Toolbar
        ctrl = QHBoxLayout()

        self._lbl_count = QLabel("Записей: 0")
        self._lbl_count.setStyleSheet("color: #a6adc8; font-size: 12px;")
        ctrl.addWidget(self._lbl_count)

        ctrl.addStretch()

        self._btn_clear = QPushButton("🗑  Очистить")
        self._btn_clear.setFixedHeight(26)
        self._btn_clear.clicked.connect(self._on_clear)
        ctrl.addWidget(self._btn_clear)

        self._cb_format = QComboBox()
        self._cb_format.addItem("CSV", "csv")
        self._cb_format.addItem("XLSX", "xlsx")
        self._cb_format.setFixedHeight(26)
        ctrl.addWidget(self._cb_format)

        self._btn_export = QPushButton("💾  Экспорт")
        self._btn_export.setFixedHeight(26)
        self._btn_export.setProperty("class", "primary-btn")
        self._btn_export.clicked.connect(self._on_export)
        ctrl.addWidget(self._btn_export)

        root.addLayout(ctrl)

        # Таблица
        self._table = QTableWidget()
        self._table.setColumnCount(len(ExperimentData.HEADERS))
        self._table.setHorizontalHeaderLabels(ExperimentData.HEADERS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setDefaultSectionSize(22)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setGridStyle(Qt.PenStyle.SolidLine)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        self._table.setStyleSheet("""
            QTableWidget {
                background: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                gridline-color: #313244;
                font-size: 12px;
            }
            QTableWidget::item { padding: 2px 6px; }
            QTableWidget::item:selected {
                background: #313244;
                color: #cba6f7;
            }
            QHeaderView::section {
                background: #181825;
                color: #89b4fa;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 4px;
            }
        """)

        root.addWidget(self._table)

    # ----------------------------------------------------------------- API --

    def notify_new_data(self):
        """Вызывать при добавлении новых строк в ExperimentData."""
        self._pending = True

    def _flush(self):
        if not self._pending:
            return
        self._pending = False

        total = len(self._data)
        if total == 0:
            return

        self._lbl_count.setText(f"Записей: {total}")

        # Добавляем только новые строки
        start = self._displayed_rows
        end = min(total, MAX_DISPLAY_ROWS)

        if start >= end:
            return

        self._table.setRowCount(end)

        for i in range(start, end):
            cells = self._data.row_as_display(i)
            bg = _ROW_EVEN if i % 2 == 0 else _ROW_ODD
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                item.setBackground(bg)
                item.setForeground(_TEXT_COLOR)
                self._table.setItem(i, col, item)

        self._displayed_rows = end

        # Автопрокрутка вниз
        self._table.scrollToBottom()

    def _on_clear(self):
        self._data.clear()
        self._displayed_rows = 0
        self._table.setRowCount(0)
        self._lbl_count.setText("Записей: 0")

    def _on_export(self):
        if len(self._data) == 0:
            QMessageBox.warning(self, "Экспорт", "Нет данных для экспорта.")
            return

        fmt = self._cb_format.currentData()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"speedsensor_{ts}.{fmt}"

        if fmt == "csv":
            path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить CSV", default_name,
                "CSV файлы (*.csv);;Все файлы (*)"
            )
            if path:
                self._data.export_csv(path)
                self._show_success(path)

        elif fmt == "xlsx":
            path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить XLSX", default_name,
                "Excel файлы (*.xlsx);;Все файлы (*)"
            )
            if path:
                self._data.export_xlsx(path)
                self._show_success(path)

    def _show_success(self, path: str):
        QMessageBox.information(
            self, "Экспорт завершён",
            f"Файл сохранён:\n{path}\n\nЗаписей: {len(self._data)}"
        )
