from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self, app_name: str) -> None:
        super().__init__()
        self.setWindowTitle(app_name)
        self.setCentralWidget(QLabel(f"{app_name} is ready"))
