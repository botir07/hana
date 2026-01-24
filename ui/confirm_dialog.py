from PySide6.QtWidgets import QMessageBox, QWidget


class ConfirmDialog:
    @staticmethod
    def confirm(parent: QWidget, message: str) -> bool:
        reply = QMessageBox.question(parent, "Confirm", message, QMessageBox.Yes | QMessageBox.No)
        return reply == QMessageBox.Yes
