# ui/avatar_view.py
import os
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData, Filename


class _PandaApp(ShowBase):
    def __init__(self, model_path: str):
        # Panda3D oynasini Qt ichida ishlatish uchun alohida window ochmaslikka harakat qilamiz
        loadPrcFileData("", "window-type none")
        loadPrcFileData("", "audio-library-name null")
        super().__init__()

        self.model = None
        self.angle = 0.0

        # Offscreen buffer yaratib, keyin Qtga berish murakkabroq.
        # Shuning uchun eng tez MVP: Panda3D alohida oynada render qiladi.
        # (Keyin xohlasang Qt ichiga embed ham qilamiz.)

        self.openDefaultWindow()

        self.disableMouse()
        self.cam.setPos(0, -4, 1.6)
        self.cam.lookAt(0, 0, 1.0)

        if os.path.exists(model_path):
            p = Filename.fromOsSpecific(model_path)
            self.model = self.loader.loadModel(p)
            self.model.reparentTo(self.render)
            self.model.setPos(0, 0, 0)
        else:
            self.model = None

        # Light
        from panda3d.core import AmbientLight, DirectionalLight
        al = AmbientLight("al")
        al.setColor((0.6, 0.6, 0.6, 1))
        al_np = self.render.attachNewNode(al)
        self.render.setLight(al_np)

        dl = DirectionalLight("dl")
        dl.setColor((0.9, 0.9, 0.9, 1))
        dl_np = self.render.attachNewNode(dl)
        dl_np.setHpr(45, -45, 0)
        self.render.setLight(dl_np)

    def step(self):
        if self.model:
            self.angle = (self.angle + 0.5) % 360.0
            self.model.setH(self.angle)


class AvatarView(QWidget):
    """
    MVP: Panda3D alohida oynada ko‘rsatadi.
    (Agar xohlasang keyingi bosqichda Qt widget ichiga embed qilamiz.)
    """
    def __init__(self, model_path: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("3D avatar (Panda3D window)"))

        self._app = _PandaApp(model_path)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60fps

    def _tick(self):
        self._app.step()
        self._app.taskMgr.step()
