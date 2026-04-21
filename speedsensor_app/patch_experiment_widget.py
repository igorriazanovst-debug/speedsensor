#!/usr/bin/env python3
"""
Патч: заменяет ui/experiment_widget.py рабочей версией с исправлениями:
  1. Авто-центрирование и авто-масштаб при смене единиц измерения
  2. Настройка вида линии графика (цвет, толщина, тип, маркеры)
  3. Кеширование numpy-массивов (производительность)
  4. QueuedConnection для thread-safety

Запуск: python patch_experiment_widget.py <путь_к_speedsensor_app>
"""
import sys
import os
import shutil

def main():
    if len(sys.argv) < 2:
        print("Использование: python patch_experiment_widget.py <путь_к_speedsensor_app>")
        sys.exit(1)

    base = sys.argv[1].rstrip("/\\")
    if not os.path.isdir(base):
        print(f"Директория не найдена: {base}")
        sys.exit(1)

    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_widget.py")
    dst = os.path.join(base, "ui", "experiment_widget.py")

    if not os.path.exists(src):
        print(f"Файл-источник не найден: {src}")
        print("Убедитесь, что experiment_widget.py лежит рядом с этим скриптом.")
        sys.exit(1)

    if not os.path.exists(dst):
        print(f"Целевой файл не найден: {dst}")
        sys.exit(1)

    # Бэкап
    bak = dst + ".bak"
    shutil.copy2(dst, bak)
    print(f"  Бэкап: {bak}")

    shutil.copy2(src, dst)
    print(f"  ✓ {dst}")
    print("Готово.")

if __name__ == "__main__":
    main()
