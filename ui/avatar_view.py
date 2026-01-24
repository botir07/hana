import os

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

try:
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtQml import QQmlContext
    QTQUICK_AVAILABLE = True
except ImportError:
    QTQUICK_AVAILABLE = False


class AvatarView(QWidget):
    def __init__(self, model_path: str) -> None:
        super().__init__()
        if not QTQUICK_AVAILABLE:
            layout = QVBoxLayout()
            label = QLabel("QtQuick3D is not available. Install PySide6-Addons to enable 3D.")
            label.setWordWrap(True)
            layout.addWidget(label)
            self.setLayout(layout)
            return

        qml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "avatar_view.qml"))
        if not os.path.exists(qml_path):
            layout = QVBoxLayout()
            label = QLabel("avatar_view.qml not found.")
            label.setWordWrap(True)
            layout.addWidget(label)
            self.setLayout(layout)
            return

        layout = QVBoxLayout()
        self._view = QQuickWidget()
        self._view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        context: QQmlContext = self._view.rootContext()
        if os.path.exists(model_path):
            context.setContextProperty("modelPath", QUrl.fromLocalFile(model_path))
        else:
            context.setContextProperty("modelPath", QUrl())
        self._view.setSource(QUrl.fromLocalFile(qml_path))
        layout.addWidget(self._view)
        self.setLayout(layout)
