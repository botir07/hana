import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from core.config import Config


class AvatarWindow(QWidget):
    def __init__(self, chat_window: QWidget) -> None:
        super().__init__()
        self._config = Config()
        self._chat_window = chat_window
        self._drag_offset = QPoint()
        mode = os.environ.get("HANA_AVATAR_MODE", self._config.avatar_mode).strip().lower()
        self._is_2d = mode.startswith("2")

        self.setWindowTitle("HANA Avatar")
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        model_path = os.path.join(base_dir, "assets", "chisa", "Chisa.fbx")

        if self._is_2d:
            from ui.avatar_2d import Avatar2D  # local import to avoid Panda3D when unused

            assets_dir = os.path.join(base_dir, "assets", "waifu2d")
            self._avatar = Avatar2D(assets_dir=assets_dir, on_chat=self._toggle_chat, on_quit=self._quit)
        else:
            from ui.avatar_view import AvatarView  # Panda3D renderer

            self._avatar = AvatarView(model_path, on_chat=self._toggle_chat, on_quit=self._quit)
        if hasattr(self._chat_window, "set_avatar_window"):
            self._chat_window.set_avatar_window(self)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._avatar)
        self.setLayout(layout)

        if self._is_2d:
            hint = self._avatar.sizeHint()
            self.setFixedSize(hint)
            self.setWindowOpacity(0.98)
            self.move(80, 80)
        else:
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

    def mousePressEvent(self, event) -> None:
        if not self._is_2d:
            return super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._is_2d:
            return super().mouseMoveEvent(event)
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)
