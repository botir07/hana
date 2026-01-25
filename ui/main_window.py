from PySide6.QtCore import QThread, Signal
import os

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QInputDialog,
    QLabel,
    QHBoxLayout,
)

from core.agent import Agent
from core.executor import Executor
from ui.avatar_view import AvatarView
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
        self.setWindowTitle("HANA")
        self._agent = Agent()
        self._executor = Executor()
        self._worker = None

        self._chat = QTextEdit()
        self._chat.setReadOnly(True)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a request...")
        self._input.returnPressed.connect(self._on_send)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._on_send)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self._chat)
        left_layout.addWidget(self._input)
        left_layout.addWidget(self._send_btn)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        model_path = os.path.join(base_dir, "assets", "anime+girl+3d+model.glb")
        self._avatar = AvatarView(model_path)
        self._status = QLabel("HANA ready.")
        self._status.setWordWrap(True)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self._avatar)
        right_layout.addWidget(self._status)

        layout = QHBoxLayout()
        layout.addLayout(left_layout, 3)
        layout.addLayout(right_layout, 2)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _set_busy(self, busy: bool) -> None:
        self._send_btn.setEnabled(not busy)
        self._input.setEnabled(not busy)

    def _append_chat(self, role: str, message: str) -> None:
        self._chat.append(f"{role}: {message}")
        if role == "HANA":
            self._status.setText(message)

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        if not self._agent.has_api_key():
            api_key, ok = QInputDialog.getText(self, "OpenRouter API Key", "Enter OpenRouter API key:")
            api_key = api_key.strip()
            if not ok or not api_key:
                QMessageBox.warning(self, "Missing API Key", "OpenRouter API key is required to continue.")
                return
            self._agent.set_api_key(api_key)
        self._input.clear()
        self._append_chat("User", text)
        self._set_busy(True)

        self._worker = AgentWorker(self._agent, text)
        self._worker.finished.connect(self._on_agent_result)
        self._worker.failed.connect(self._on_agent_error)
        self._worker.start()

    def _on_agent_result(self, result: dict) -> None:
        self._set_busy(False)
        if result.get("type") == "reply":
            self._append_chat("HANA", result.get("message", ""))
            return

        if result.get("type") == "action":
            self._handle_action(result)
            return

        self._append_chat("HANA", "Unexpected response from agent.")

    def _on_agent_error(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "Agent Error", message)

    def _handle_action(self, result: dict) -> None:
        action = result.get("action")
        args = result.get("args", {})
        preface = result.get("message")
        if preface:
            self._append_chat("HANA", preface)

        outcome = self._executor.execute_action(action, args, confirmed=False)
        if outcome.get("status") == "needs_confirmation":
            confirm = ConfirmDialog.confirm(self, outcome.get("message", "Confirm action?"))
            if not confirm:
                self._append_chat("HANA", "Action cancelled.")
                return
            outcome = self._executor.execute_action(action, args, confirmed=True)

        self._append_chat("HANA", outcome.get("message", "Action completed."))
