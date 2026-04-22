import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale
from ui.main_window import MainWindow
from core.settings import AppSettings

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SpeedSensor Lab")
    app.setOrganizationName("SpeedSensorLab")

    settings = AppSettings()

    translator = QTranslator()
    lang = settings.get("language", "ru")
    translator.load(f"locales/{lang}.qm")
    app.installTranslator(translator)

    window = MainWindow(settings)
    window.showMaximized()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
