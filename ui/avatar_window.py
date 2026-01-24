import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMenu

from ui.avatar_view import AvatarView


class AvatarWindow(QWidget):
    def __init__(self, chat_window: QWidget) -> None:
        super().__init__()
        self._chat_window = chat_window
        self.setWindowTitle("HANA Avatar")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        model_path = os.path.join(base_dir, "assets", "anime+girl+3d+model.glb")
        self._avatar = AvatarView(model_path)

        layout = QVBoxLayout()
        layout.addWidget(self._avatar)
        self.setLayout(layout)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        chat_action = menu.addAction("Chat")
        quit_action = menu.addAction("Quit")
        action = menu.exec(event.globalPos())
        if action == chat_action:
            if hasattr(self._chat_window, "toggle_visible"):
                self._chat_window.toggle_visible()
            else:
                self._chat_window.show()
        elif action == quit_action:
            self.close()
