import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.avatar_window import AvatarWindow


def main() -> int:
    app = QApplication(sys.argv)
    chat_window = MainWindow()
    chat_window.hide()
    avatar_window = AvatarWindow(chat_window)
    avatar_window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
