from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)


class ScreenOverlay(QWidget):
    """Small always-on-top window to show OCR output."""

    def __init__(self, on_close: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._on_close = on_close
        self.setWindowTitle("Screen OCR")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(360)

        title = QLabel("Screen OCR")
        title.setStyleSheet("color: white; font-weight: 600;")

        close_btn = QPushButton("×")
        close_btn.setFixedWidth(24)
        close_btn.clicked.connect(self._handle_close)

        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlaceholderText("No OCR yet...")

        layout = QVBoxLayout()
        layout.addLayout(header)
        layout.addWidget(self._text)

        container = QWidget()
        container.setObjectName("overlayCard")
        container.setLayout(layout)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.addWidget(container)

        self.setStyleSheet(
            "#overlayCard {"
            "background-color: rgba(24, 24, 26, 210);"
            "border: 1px solid rgba(255, 255, 255, 40);"
            "border-radius: 10px;"
            "padding: 8px;"
            "}"
            "QTextEdit {"
            "background-color: rgba(40, 40, 44, 190);"
            "color: white;"
            "border: 1px solid rgba(255, 255, 255, 40);"
            "border-radius: 6px;"
            "}"
            "QPushButton {"
            "background-color: rgba(70, 70, 70, 200);"
            "color: white;"
            "border-radius: 6px;"
            "padding: 4px;"
            "}"
        )

    def append_text(self, text: str) -> None:
        self._text.append(text)
        self._text.moveCursor(QTextCursor.End)
        self._text.ensureCursorVisible()

    def clear_text(self) -> None:
        self._text.clear()

    def _handle_close(self) -> None:
        self.hide()
        self.clear_text()
        if self._on_close:
            self._on_close()
