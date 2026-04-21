"""
fix_table_lag.py — исправляет тормоза в data_table.py.

Проблема: _flush() добавляет ВСЕ накопившиеся строки за один вызов.
При sample_rate=50 Гц за 20 сек = 1000 строк × 5 столбцов = 5000 QTableWidgetItem
создаётся разом, плюс setRowCount() пересчитывает layout, scrollToBottom() тоже.

Решение:
  1. Ограничить батч: за один _flush не более BATCH_SIZE строк
  2. Обернуть в setUpdatesEnabled(False/True) — отключить промежуточные repaints
  3. scrollToBottom() только если был прогресс
  4. Уменьшить интервал _flush до 50 мс (плавнее, но меньше строк за раз)

Запуск: python fix_table_lag.py <путь до speedsensor_app>
"""

import sys
import re
import os
import shutil
from pathlib import Path

BATCH_SIZE = 50          # строк за один _flush
FLUSH_INTERVAL_MS = 50  # мс между flush-вызовами


def patch(target: Path):
    src = target.read_text(encoding="utf-8")

    # --- 1. Интервал таймера ---
    src = re.sub(
        r"(self\._flush_timer\.setInterval\()\d+(\))",
        rf"\g<1>{FLUSH_INTERVAL_MS}\g<2>",
        src,
    )

    # --- 2. Метод _flush: батч + setUpdatesEnabled ---
    old_flush = r"""    def _flush\(self\):
        if not self\._pending:
            return
        self\._pending = False

        total = len\(self\._data\)
        if total == 0:
            return

        self\._lbl_count\.setText\(f"Записей: \{total\}"\)

        # Добавляем только новые строки
        start = self\._displayed_rows
        end = min\(total, MAX_DISPLAY_ROWS\)

        if start >= end:
            return

        self\._table\.setRowCount\(end\)

        for i in range\(start, end\):
            cells = self\._data\.row_as_display\(i\)
            bg = _ROW_EVEN if i % 2 == 0 else _ROW_ODD
            for col, val in enumerate\(cells\):
                item = QTableWidgetItem\(val\)
                item\.setTextAlignment\(
                    Qt\.AlignmentFlag\.AlignRight \| Qt\.AlignmentFlag\.AlignVCenter
                \)
                item\.setBackground\(bg\)
                item\.setForeground\(_TEXT_COLOR\)
                self\._table\.setItem\(i, col, item\)

        self\._displayed_rows = end

        # Автопрокрутка вниз
        self\._table\.scrollToBottom\(\)"""

    new_flush = f"""    def _flush(self):
        if not self._pending:
            return

        total = len(self._data)
        if total == 0:
            return

        self._lbl_count.setText(f"Записей: {{total}}")

        start = self._displayed_rows
        end = min(total, MAX_DISPLAY_ROWS)

        if start >= end:
            self._pending = False
            return

        # Ограничиваем батч — не более {BATCH_SIZE} строк за один вызов
        batch_end = min(end, start + {BATCH_SIZE})

        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(batch_end)

        for i in range(start, batch_end):
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

        self._table.setUpdatesEnabled(True)
        self._displayed_rows = batch_end

        # Автопрокрутка вниз
        self._table.scrollToBottom()

        # Если остались строки — оставить флаг, чтобы следующий тик добил их
        if batch_end < end:
            self._pending = True
        else:
            self._pending = False"""

    new_src, n = re.subn(old_flush, new_flush, src, flags=re.DOTALL)

    if n == 0:
        # Попробуем более простой подход — просто добавим ограничение батча
        print("  WARN: точный regex не совпал, применяем упрощённый патч")
        new_src = _simple_patch(src)
        if new_src == src:
            print("  ERROR: не удалось применить патч автоматически")
            print("         Примените вручную: ограничьте batch в _flush,")
            print("         добавьте setUpdatesEnabled(False/True)")
            return False

    # Бэкап
    bak = target.with_suffix(".py.bak_lag")
    shutil.copy2(target, bak)
    print(f"  BAK  {bak.name}")

    target.write_text(new_src, encoding="utf-8")
    print(f"  OK   {target}")
    return True


def _simple_patch(src: str) -> str:
    """Вставляем ограничение батча в существующий _flush через простую замену."""

    # Заменяем конец range(start, end) на батч
    src = src.replace(
        "        for i in range(start, end):",
        f"        batch_end = min(end, start + {BATCH_SIZE})\n"
        "        self._table.setUpdatesEnabled(False)\n"
        "        for i in range(start, batch_end):",
    )
    src = src.replace(
        "        self._displayed_rows = end\n\n        # Автопрокрутка вниз\n        self._table.scrollToBottom()",
        "        self._table.setUpdatesEnabled(True)\n"
        "        self._displayed_rows = batch_end\n\n"
        "        # Автопрокрутка вниз\n"
        "        self._table.scrollToBottom()\n\n"
        "        # Остались строки — следующий тик заберёт\n"
        "        if batch_end < end:\n"
        "            self._pending = True\n"
        "        else:\n"
        "            self._pending = False",
    )
    # Убираем self._pending = False в начале _flush (теперь управляем им сами)
    src = src.replace(
        "        self._pending = False\n\n        total = len(self._data)",
        "        total = len(self._data)",
    )
    return src


def main():
    if len(sys.argv) < 2:
        print(f"Использование: python {sys.argv[0]} <путь до speedsensor_app>")
        sys.exit(1)

    app_dir = Path(sys.argv[1])
    target = app_dir / "ui" / "widgets" / "data_table.py"

    if not target.exists():
        print(f"Файл не найден: {target}")
        sys.exit(1)

    print(f"Патч: {target}")
    ok = patch(target)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
