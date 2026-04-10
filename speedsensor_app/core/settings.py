from PySide6.QtCore import QSettings


class AppSettings:
    def __init__(self):
        self._qs = QSettings("SpeedSensorLab", "SpeedSensorApp")

    def get(self, key: str, default=None):
        return self._qs.value(key, default)

    def set(self, key: str, value):
        self._qs.setValue(key, value)
        self._qs.sync()

    def get_all(self) -> dict:
        result = {}
        for key in self._qs.allKeys():
            result[key] = self._qs.value(key)
        return result
