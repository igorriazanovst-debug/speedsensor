"""
Патч experiment_widget.py:
  При tooltip_follow=False и остановленном эксперименте движение мыши
  по графику обновляет _static_info из кешированных данных.

Запуск из папки speedsensor_app:
    python patch_static_tooltip_stopped.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(BASE, "speedsensor_app")):
    BASE = os.path.join(BASE, "speedsensor_app")
print(f"[patch] Корень проекта: {BASE}")

EW_PATH = os.path.join(BASE, "ui", "experiment_widget.py")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  OK  {os.path.relpath(path, BASE)}")

def patch_once(path, old, new, label=""):
    text = read(path)
    if old not in text:
        print(f"  --  не найден ({label})")
        return False
    if new in text:
        print(f"  ~~  уже применён ({label})")
        return False
    write(path, text.replace(old, new, 1))
    return True


# Заменяем блок в _on_mouse_move:
# было: если tooltip_follow=False — просто return
# стало: если tooltip_follow=False — обновляем _static_info по позиции курсора

OLD = """\
        # В статичном режиме курсор на графике не обрабатываем
        if not self._tooltip_follow:
            return"""

NEW = """\
        # В статичном режиме — обновляем _static_info по позиции курсора
        if not self._tooltip_follow:
            if self._t_cache.size == 0:
                return
            mouse_point = pw.getPlotItem().vb.mapSceneToView(pos)
            mx = mouse_point.x()
            ta = self._t_cache
            ya_disp = self._y_cache
            ya_raw = self._y_raw_cache
            idx = int(np.argmin(np.abs(ta - mx)))
            snap_t = ta[idx]
            snap_y = ya_disp[idx]
            snap_omega = ya_raw[idx]
            # Перекрестие и точка
            self._vline.setPos(snap_t)
            self._hline.setPos(snap_y)
            self._vline.setVisible(True)
            self._hline.setVisible(True)
            self._snap_dot.setData([snap_t], [snap_y])
            self._snap_dot.setVisible(True)
            # Обновить статичный блок
            rps = snap_omega / (2.0 * math.pi)
            rpm = rps * 60.0
            diam = self._exp_data.disk_diameter_mm
            v = snap_omega * (diam / 2.0)
            unit_str = "рад/с" if self._unit == UNIT_RAD_S else "об/с"
            disp = snap_omega / (2.0 * math.pi) if self._unit == UNIT_RPS else snap_omega
            self._static_info.setText(
                f"t={snap_t:.2f}с  ω={disp:.3f} {unit_str}  "
                f"об/с={rps:.3f}  RPM={rpm:.1f}  V={v:.1f} мм/с"
            )
            return"""

patch_once(EW_PATH, OLD, NEW, "_on_mouse_move static branch")

# Также: при выходе мыши за пределы графика в static-режиме
# скрываем перекрестие (сейчас _on_mouse_hover это делает — ок)
# но при выходе через sceneBoundingRect нужно тоже скрывать
# (уже есть в начале _on_mouse_move — ok)

print("\n[patch] Готово.")
