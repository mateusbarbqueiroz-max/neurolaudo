import sys

from PySide6.QtWidgets import QApplication

from neurolaudo.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NeuroLaudo")
    win = MainWindow()
    if len(sys.argv) > 1:
        win.open_folder(sys.argv[1])
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
