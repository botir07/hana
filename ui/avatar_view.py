# ui/avatar_view.py
import os
import builtins
import ctypes
import math
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from direct.showbase.ShowBase import ShowBase
from direct.actor.Actor import Actor
from panda3d.core import loadPrcFileData, Filename, WindowProperties, Material


_PANDA_APP = None


class _PandaApp(ShowBase):
    def __init__(self, model_path: str, on_chat, on_quit):
        # Panda3D oynasini Qt ichida ishlatish uchun alohida window ochmaslikka harakat qilamiz
        loadPrcFileData("", "window-type none")
        loadPrcFileData("", "audio-library-name null")
        loadPrcFileData("", "textures-power-2 none")
        loadPrcFileData("", "win-title HANA Avatar")
        super().__init__()

        self.model = None
        self.angle = 0.0
        self.tilt = 0.0
        self._base_z = 0.0
        self._spin_speed = 0.6
        self._bob_amp = 0.08
        self._state = "idle"
        self._menu = None
        self._on_chat = on_chat
        self._on_quit = on_quit

        # Offscreen buffer yaratib, keyin Qtga berish murakkabroq.
        # Shuning uchun eng tez MVP: Panda3D alohida oynada render qiladi.
        # (Keyin xohlasang Qt ichiga embed ham qilamiz.)

        self.openDefaultWindow()
        try:
            props = WindowProperties()
            props.setTitle("HANA Avatar")
            self.win.requestProperties(props)
        except Exception:
            pass
        self._set_topmost()

        self.disableMouse()
        self.cam.setPos(0, -5.5, 2.2)
        self.cam.lookAt(0, 0, 1.2)
        self.setBackgroundColor(0.08, 0.08, 0.09, 1.0)
        self.render.setShaderAuto()
        self.render.setAntialias(True)

        self.load_model(model_path)

        # Light
        from panda3d.core import AmbientLight, DirectionalLight, PointLight
        self._al = AmbientLight("al")
        self._al.setColor((0.65, 0.65, 0.7, 1))
        self._al_np = self.render.attachNewNode(self._al)
        self.render.setLight(self._al_np)

        self._dl = DirectionalLight("dl")
        self._dl.setColor((1.2, 1.15, 1.05, 1))
        self._dl_np = self.render.attachNewNode(self._dl)
        self._dl_np.setHpr(30, -35, 0)
        self.render.setLight(self._dl_np)

        self._pl = PointLight("pl")
        self._pl.setColor((1.2, 1.1, 1.4, 1))
        self._pl_np = self.render.attachNewNode(self._pl)
        self._pl_np.setPos(2, -2, 3)
        self.render.setLight(self._pl_np)

        self.accept("mouse3", self._toggle_menu)

    def _set_topmost(self) -> None:
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "HANA Avatar")
            if hwnd:
                ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            return

    def load_model(self, model_path: str) -> None:
        if self.model:
            self.model.removeNode()
            self.model = None
        if os.path.exists(model_path):
            p = Filename.fromOsSpecific(model_path)
            actor = None
            try:
                actor = Actor(p)
            except Exception:
                actor = None
            if actor and actor.getAnimNames():
                anim_name = actor.getAnimNames()[0]
                actor.loop(anim_name)
                self.model = actor
            else:
                self.model = self.loader.loadModel(p)
            self.model.reparentTo(self.render)
            self.model.setHpr(0, 0, 0)
            self.model.setTwoSided(True)
            self.model.setShaderAuto()
            self._apply_material()
            self._fit_model()

    def _fit_model(self) -> None:
        if not self.model:
            return
        bounds = self.model.getTightBounds()
        if not bounds or bounds[0] is None or bounds[1] is None:
            self.model.setScale(1.0)
            self.model.setPos(0, 0, 0)
            return
        min_pt, max_pt = bounds
        size = max_pt - min_pt
        max_dim = max(size.x, size.y, size.z, 1.0)
        scale = 2.0 / max_dim
        center = (min_pt + max_pt) * 0.5
        self.model.setScale(scale)
        self._base_z = -center.z * scale + 0.6
        self.model.setPos(-center.x * scale, -center.y * scale, self._base_z)

    def _apply_material(self) -> None:
        if not self.model:
            return
        mat = Material()
        mat.setAmbient((0.8, 0.8, 0.85, 1))
        mat.setDiffuse((1.0, 1.0, 1.0, 1))
        mat.setSpecular((0.4, 0.4, 0.45, 1))
        mat.setShininess(8.0)
        self.model.setMaterial(mat, 1)

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "listening":
            self._spin_speed = 0.9
            self._bob_amp = 0.12
            self._al.setColor((0.25, 0.45, 0.55, 1))
        elif state == "thinking":
            self._spin_speed = 0.4
            self._bob_amp = 0.05
            self._al.setColor((0.35, 0.35, 0.4, 1))
        elif state == "speaking":
            self._spin_speed = 1.2
            self._bob_amp = 0.16
            self._al.setColor((0.45, 0.35, 0.3, 1))
        elif state == "error":
            self._spin_speed = 0.2
            self._bob_amp = 0.03
            self._al.setColor((0.6, 0.2, 0.2, 1))
        else:
            self._spin_speed = 0.6
            self._bob_amp = 0.08
            self._al.setColor((0.35, 0.35, 0.4, 1))
    def step(self):
        if self.model:
            self.angle = (self.angle + self._spin_speed) % 360.0
            self.tilt = (self.tilt + 2.0) % 360.0
            self.model.setH(self.angle)
            self.model.setP(2.0 * math.sin(self.tilt * 0.0174533))
            self.model.setZ(self._base_z + self._bob_amp * math.sin(self.tilt * 0.0174533))

    def _toggle_menu(self) -> None:
        if self._menu:
            self._menu.destroy()
            self._menu = None
            return
        from direct.gui.DirectGui import DirectFrame, DirectButton
        self._menu = DirectFrame(
            frameColor=(0.05, 0.05, 0.06, 0.85),
            frameSize=(10, 190, -90, -10),
            pos=(0, 0, 0),
            parent=self.pixel2d,
        )
        DirectButton(
            parent=self._menu,
            text="Chat",
            scale=0.05,
            pos=(100, 0, -35),
            command=self._on_chat,
        )
        DirectButton(
            parent=self._menu,
            text="Quit",
            scale=0.05,
            pos=(100, 0, -70),
            command=self._on_quit,
        )


class AvatarView(QWidget):
    """
    MVP: Panda3D alohida oynada ko‘rsatadi.
    (Agar xohlasang keyingi bosqichda Qt widget ichiga embed qilamiz.)
    """
    def __init__(self, model_path: str, on_chat=None, on_quit=None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("3D avatar (Panda3D window)"))

        self._app = self._get_app(model_path, on_chat, on_quit)
        if self._app is None:
            layout.addWidget(QLabel("Panda3D is already running. Restart the app."))
            return

        self._stepping = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30fps

    def _tick(self):
        if self._stepping:
            return
        self._stepping = True
        try:
            self._app.step()
            self._app.taskMgr.step()
        finally:
            self._stepping = False

    def _get_app(self, model_path: str, on_chat, on_quit):
        global _PANDA_APP
        if _PANDA_APP is not None:
            _PANDA_APP.load_model(model_path)
            return _PANDA_APP
        existing = getattr(builtins, "base", None)
        if existing is not None:
            return None
        _PANDA_APP = _PandaApp(model_path, on_chat, on_quit)
        return _PANDA_APP

    def set_state(self, state: str) -> None:
        if self._app:
            self._app.set_state(state)
