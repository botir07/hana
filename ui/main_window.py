from PySide6.QtCore import Qt, QPoint, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.agent import Agent
from core.config import Config
from core.executor import Executor
from core.tts import TTSPlayer
from ui.confirm_dialog import ConfirmDialog


class AgentWorker(QThread):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, agent: Agent, text: str) -> None:
        super().__init__()
        self._agent = agent
        self._text = text

    def run(self) -> None:
        try:
            result = self._agent.process_text(self._text)
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover - UI thread safety
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AIRI Chat")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.92)

        self._agent = Agent()
        self._config = Config()
        self._executor = Executor()
        self._worker = None
        self._drag_offset = QPoint()
        self._avatar_window = None
        self._tts = TTSPlayer(self._config.tts_voice)

        self._chat = QTextEdit()
        self._chat.setReadOnly(True)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a request...")
        self._input.returnPressed.connect(self._on_send)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._on_send)

        menu_btn = QToolButton()
        menu_btn.setText("Settings")
        menu = QMenu(menu_btn)
        set_key_action = menu.addAction("Set OpenRouter API Key")
        set_key_action.triggered.connect(self._on_set_api_key)
        menu_btn.setMenu(menu)
        menu_btn.setPopupMode(QToolButton.InstantPopup)

        title = QLabel("AIRI")
        title.setStyleSheet("color: white; font-weight: 600;")

        min_btn = QPushButton("-")
        min_btn.setFixedWidth(24)
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("x")
        close_btn.setFixedWidth(24)
        close_btn.clicked.connect(self.hide)

        header = QHBoxLayout()
        header.addWidget(menu_btn)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(min_btn)
        header.addWidget(close_btn)

        content_layout = QVBoxLayout()
        content_layout.addLayout(header)
        content_layout.addWidget(self._chat)
        content_layout.addWidget(self._input)
        content_layout.addWidget(self._send_btn)

        card = QWidget()
        card.setObjectName("chatCard")
        card.setLayout(content_layout)

        outer = QVBoxLayout()
        outer.addWidget(card)

        container = QWidget()
        container.setLayout(outer)
        container.setStyleSheet(
            "#chatCard {"
            "background-color: rgba(24, 24, 26, 150);"
            "border: 1px solid rgba(255, 255, 255, 40);"
            "border-radius: 10px;"
            "padding: 8px;"
            "}"
            "QTextEdit, QLineEdit {"
            "background-color: rgba(40, 40, 44, 170);"
            "color: white;"
            "border: 1px solid rgba(255, 255, 255, 40);"
            "border-radius: 6px;"
            "}"
            "QPushButton, QToolButton {"
            "background-color: rgba(70, 70, 70, 180);"
            "color: white;"
            "border-radius: 6px;"
            "padding: 6px;"
            "}"
        )
        self.setCentralWidget(container)

    def _set_busy(self, busy: bool) -> None:
        self._send_btn.setEnabled(not busy)
        self._input.setEnabled(not busy)

    def _append_chat(self, role: str, message: str) -> None:
        self._chat.append(f"{role}: {message}")
        if role == "AIRI":
            self._tts.speak(message)

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._set_avatar_state("listening")
        if not self._agent.has_api_key():
            if not self._prompt_api_key():
                QMessageBox.warning(self, "Missing API Key", "OpenRouter API key is required to continue.")
                return
        self._input.clear()
        self._append_chat("User", text)
        self._set_busy(True)
        self._set_avatar_state("thinking")

        self._worker = AgentWorker(self._agent, text)
        self._worker.finished.connect(self._on_agent_result)
        self._worker.failed.connect(self._on_agent_error)
        self._worker.start()

    def _on_agent_result(self, result: dict) -> None:
        self._set_busy(False)
        if result.get("type") == "reply":
            self._append_chat("AIRI", result.get("message", ""))
            self._set_avatar_state("speaking")
            QTimer.singleShot(2000, lambda: self._set_avatar_state("idle"))
            return

        if result.get("type") == "action":
            self._handle_action(result)
            return

        self._append_chat("AIRI", "Unexpected response from agent.")

    def _on_agent_error(self, message: str) -> None:
        self._set_busy(False)
        self._set_avatar_state("error")
        QMessageBox.critical(self, "Agent Error", message)

    def _handle_action(self, result: dict) -> None:
        action = result.get("action")
        args = result.get("args", {})
        preface = result.get("message")
        if preface:
            self._append_chat("AIRI", preface)

        outcome = self._executor.execute_action(action, args, confirmed=False)
        if outcome.get("status") == "needs_confirmation":
            confirm = ConfirmDialog.confirm(self, outcome.get("message", "Confirm action?"))
            if not confirm:
                self._append_chat("AIRI", "Action cancelled.")
                self._set_avatar_state("idle")
                return
            outcome = self._executor.execute_action(action, args, confirmed=True)

        self._append_chat("AIRI", outcome.get("message", "Action completed."))
        QTimer.singleShot(2000, lambda: self._set_avatar_state("idle"))

    def _on_set_api_key(self) -> None:
        if self._prompt_api_key():
            QMessageBox.information(self, "API Key", "OpenRouter API key saved.")

    def _prompt_api_key(self) -> bool:
        api_key, ok = QInputDialog.getText(
            self,
            "OpenRouter API Key",
            "Enter OpenRouter API key:",
            QLineEdit.Password,
        )
        api_key = api_key.strip()
        if not ok or not api_key:
            return False
        self._agent.set_api_key(api_key)
        return True

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def set_avatar_window(self, avatar_window) -> None:
        self._avatar_window = avatar_window

    def _set_avatar_state(self, state: str) -> None:
        if self._avatar_window and hasattr(self._avatar_window, "set_state"):
            self._avatar_window.set_state(state)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)
