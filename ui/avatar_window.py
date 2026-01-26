import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication

from ui.avatar_view import AvatarView


class AvatarWindow(QWidget):
    def __init__(self, chat_window: QWidget) -> None:
        super().__init__()
        self._chat_window = chat_window
        self.setWindowTitle("HANA Avatar")
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        model_path = os.path.join(base_dir, "assets", "arknights_endfield_-laevatain-.glb")
        self._avatar = AvatarView(model_path, on_chat=self._toggle_chat, on_quit=self._quit)
        if hasattr(self._chat_window, "set_avatar_window"):
            self._chat_window.set_avatar_window(self)

        layout = QVBoxLayout()
        layout.addWidget(self._avatar)
        self.setLayout(layout)
        self.setFixedSize(1, 1)
        self.setWindowOpacity(0.0)
        self.move(-10000, -10000)

    def _toggle_chat(self) -> None:
        if hasattr(self._chat_window, "toggle_visible"):
            self._chat_window.toggle_visible()
        else:
            self._chat_window.show()

    def _quit(self) -> None:
        QApplication.quit()

    def set_state(self, state: str) -> None:
        if hasattr(self._avatar, "set_state"):
            self._avatar.set_state(state)
