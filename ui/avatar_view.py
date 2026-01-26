# ui/avatar_view.py
import os
import builtins
import ctypes
import math
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout

from direct.showbase.ShowBase import ShowBase
from direct.actor.Actor import Actor
from panda3d.core import loadPrcFileData, Filename, WindowProperties, Material


_PANDA_APP = None


class _WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _WinRect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _PandaApp(ShowBase):
    def __init__(self, model_path: str, on_chat, on_quit):
        # Panda3D oynasini Qt ichida ishlatish uchun alohida window ochmaslikka harakat qilamiz
        loadPrcFileData("", "window-type onscreen")
        loadPrcFileData("", "win-size 520 700")
        loadPrcFileData("", "framebuffer-alpha 1")
        loadPrcFileData("", "win-transparent 1")
        loadPrcFileData("", "audio-library-name null")
        loadPrcFileData("", "textures-power-2 none")
        loadPrcFileData("", "win-title HANA Avatar")
        loadPrcFileData("", "undecorated true")
        super().__init__()

        self.model = None
        self.angle = 0.0
        self.tilt = 0.0
        self._base_z = 0.0
        self._spin_speed = 0.0
        self._bob_amp = 0.08
        self._state = "idle"
        self._menu = None
        self._on_chat = on_chat
        self._on_quit = on_quit
        self._model_error = None
        self._hwnd = None
        self._hwnd_tries = 0
        self._max_heading = 25.0
        self._max_pitch = 15.0
        self._current_h = 0.0
        self._current_p = 0.0
        self._look_smooth = 0.18
        self._dragging = False
        self._last_cursor = None
        self._cam_dist = 5.5
        self._rbutton_down = False

        # Offscreen buffer yaratib, keyin Qtga berish murakkabroq.
        # Shuning uchun eng tez MVP: Panda3D alohida oynada render qiladi.
        # (Keyin xohlasang Qt ichiga embed ham qilamiz.)

        self.openDefaultWindow()
        try:
            props = WindowProperties()
            props.setTitle("HANA Avatar")
            props.setUndecorated(True)
            props.setTransparent(True)
            self.win.requestProperties(props)
        except Exception:
            pass
        self._set_topmost()
        self._position_window()
        self.taskMgr.doMethodLater(0.2, self._ensure_window, "ensure_window")

        self.disableMouse()
        self.cam.setPos(0, -self._cam_dist, 2.2)
        self.cam.lookAt(0, 0, 1.2)
        # Use a color key for background transparency without erasing black pixels.
        self.setBackgroundColor(1.0, 0.0, 1.0, 1.0)
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

        self.accept("mouse1", self._on_drag_start)
        self.accept("mouse1-up", self._on_drag_end)
        self.accept("wheel_up", self._zoom_in)
        self.accept("wheel_down", self._zoom_out)
        self.accept("mouse3", self._toggle_menu)

    def _set_topmost(self) -> None:
        try:
            self._update_hwnd()
            if self._hwnd:
                ctypes.windll.user32.SetWindowPos(self._hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
                self._apply_layered()
        except Exception:
            return

    def _update_hwnd(self) -> None:
        if self._hwnd:
            return
        try:
            handle = self.win.getWindowHandle()
            if handle:
                self._hwnd = handle.getIntHandle()
        except Exception:
            pass
        if not self._hwnd:
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "HANA Avatar")
                if hwnd:
                    self._hwnd = hwnd
            except Exception:
                return

    def _apply_layered(self) -> None:
        if not self._hwnd:
            return
        try:
            GWL_EXSTYLE = -20
            GWL_STYLE = -16
            WS_EX_LAYERED = 0x00080000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TRANSPARENT = 0x00000020
            # Ensure the window is not click-through so mouse events reach Panda3D.
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000
            WS_MINIMIZE = 0x20000000
            WS_MAXIMIZEBOX = 0x00010000
            LWA_COLORKEY = 0x00000001
            ex_style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            ex_style = (ex_style | WS_EX_LAYERED | WS_EX_TOOLWINDOW) & ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, ex_style)
            style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_STYLE)
            style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZE | WS_MAXIMIZEBOX)
            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_STYLE, style)
            # Make magenta fully transparent; keep dark colors intact.
            ctypes.windll.user32.SetLayeredWindowAttributes(self._hwnd, 0x00FF00FF, 0, LWA_COLORKEY)
        except Exception:
            return

    def _ensure_window(self, task):
        if self._hwnd:
            self._position_window()
            return task.done
        self._hwnd_tries += 1
        self._set_topmost()
        if self._hwnd or self._hwnd_tries >= 15:
            self._position_window()
            return task.done
        return task.again

    def _position_window(self) -> None:
        if not self._hwnd:
            return
        try:
            ctypes.windll.user32.ShowWindow(self._hwnd, 5)
            ctypes.windll.user32.SetWindowPos(
                self._hwnd,
                -1,
                100,
                100,
                520,
                700,
                0x0040,
            )
        except Exception:
            return

    def _on_drag_start(self) -> None:
        self._dragging = True
        self._last_cursor = None

    def _on_drag_end(self) -> None:
        self._dragging = False
        self._last_cursor = None

    def _zoom_in(self) -> None:
        self._cam_dist = max(2.8, self._cam_dist - 0.4)
        self.cam.setY(-self._cam_dist)

    def _zoom_out(self) -> None:
        self._cam_dist = min(9.0, self._cam_dist + 0.4)
        self.cam.setY(-self._cam_dist)

    def load_model(self, model_path: str) -> bool:
        self._model_error = None
        if self.model:
            self.model.removeNode()
            self.model = None
        if os.path.exists(model_path):
            if model_path.lower().endswith((".gltf", ".glb")):
                try:
                    import gltf  # noqa: F401
                except Exception as exc:
                    self._model_error = f"panda3d-gltf import failed: {exc}"
                    return False
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
            if not self.model or self.model.isEmpty():
                self.model = None
                self._model_error = "Model load failed. Check the file and texture paths."
                return False
            self.model.reparentTo(self.render)
            self.model.setHpr(0, 0, 0)
            self.model.setTwoSided(True)
            self.model.setShaderAuto()
            self._apply_material()
            self._fit_model()
            return True
        self._model_error = "Model file not found."
        return False

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
            self._bob_amp = 0.12
            self._al.setColor((0.25, 0.45, 0.55, 1))
        elif state == "thinking":
            self._bob_amp = 0.05
            self._al.setColor((0.35, 0.35, 0.4, 1))
        elif state == "speaking":
            self._bob_amp = 0.16
            self._al.setColor((0.45, 0.35, 0.3, 1))
        elif state == "error":
            self._bob_amp = 0.03
            self._al.setColor((0.6, 0.2, 0.2, 1))
        else:
            self._bob_amp = 0.08
            self._al.setColor((0.35, 0.35, 0.4, 1))
    def _get_cursor_offset(self):
        if not self._hwnd:
            return None
        try:
            rect = _WinRect()
            if not ctypes.windll.user32.GetWindowRect(self._hwnd, ctypes.byref(rect)):
                return None
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 0 or height <= 0:
                return None
            pt = _WinPoint()
            if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                return None
            cx = rect.left + width * 0.5
            cy = rect.top + height * 0.5
            dx = (pt.x - cx) / (width * 0.5)
            dy = (pt.y - cy) / (height * 0.5)
            dx = max(-1.0, min(1.0, dx))
            dy = max(-1.0, min(1.0, dy))
            return dx, dy
        except Exception:
            return None

    def _get_cursor_pos(self):
        pt = _WinPoint()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return None
        return pt.x, pt.y

    def _get_window_rect(self):
        if not self._hwnd:
            self._update_hwnd()
        if not self._hwnd:
            return None
        rect = _WinRect()
        if not ctypes.windll.user32.GetWindowRect(self._hwnd, ctypes.byref(rect)):
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def _poll_right_click(self):
        # Fallback when the window is transparent and doesn't receive mouse events.
        VK_RBUTTON = 0x02
        state = ctypes.windll.user32.GetAsyncKeyState(VK_RBUTTON)
        down = (state & 0x8000) != 0
        if down and not self._rbutton_down:
            rect = self._get_window_rect()
            pos = self._get_cursor_pos()
            if rect and pos:
                left, top, right, bottom = rect
                if left <= pos[0] <= right and top <= pos[1] <= bottom:
                    self._toggle_menu()
        self._rbutton_down = down

    def step(self):
        if self.model:
            self.tilt = (self.tilt + 2.0) % 360.0
            self._poll_right_click()
            if self._dragging:
                pos = self._get_cursor_pos()
                if pos:
                    if self._last_cursor is not None:
                        dx = pos[0] - self._last_cursor[0]
                        dy = pos[1] - self._last_cursor[1]
                        self._current_h += dx * 0.15
                        self._current_p += dy * 0.12
                        self._current_p = max(-40.0, min(40.0, self._current_p))
                    self._last_cursor = pos
            else:
                offset = self._get_cursor_offset()
                if offset:
                    dx, dy = offset
                    target_h = -dx * self._max_heading
                    target_p = -dy * self._max_pitch
                else:
                    target_h = 0.0
                    target_p = 0.0
                self._current_h += (target_h - self._current_h) * self._look_smooth
                self._current_p += (target_p - self._current_p) * self._look_smooth
            self.model.setH(self._current_h)
            self.model.setP(self._current_p + 2.0 * math.sin(self.tilt * 0.0174533))
            self.model.setZ(self._base_z + self._bob_amp * math.sin(self.tilt * 0.0174533))

    def _toggle_menu(self) -> None:
        if self._menu:
            self._menu.destroy()
            self._menu = None
            return
        from direct.gui.DirectGui import DirectFrame, DirectButton
        pos = self._get_menu_pos()
        self._menu = DirectFrame(
            frameColor=(0.07, 0.07, 0.09, 1.0),
            frameSize=(10, 190, -90, -10),
            pos=pos,
            parent=self.pixel2d,
        )
        DirectButton(
            parent=self._menu,
            text="Chat",
            scale=0.05,
            pos=(100, 0, -35),
            frameColor=(0.15, 0.15, 0.18, 1.0),
            command=self._on_chat,
        )
        DirectButton(
            parent=self._menu,
            text="Exit",
            scale=0.05,
            pos=(100, 0, -70),
            frameColor=(0.15, 0.15, 0.18, 1.0),
            command=self._on_quit,
        )

    def _get_menu_pos(self):
        try:
            pos = self._get_cursor_pos()
            rect = self._get_window_rect()
            if not pos or not rect:
                raise RuntimeError("cursor/window not available")
            left, top, right, bottom = rect
            x_size = right - left
            y_size = bottom - top
            x = pos[0] - left
            y = pos[1] - top
            width = 180
            height = 80
            x = max(0, min(x, x_size - width))
            y = max(0, min(y, y_size - height))
            return (x, 0, y_size - y)
        except Exception:
            return (10, 0, -10)


class AvatarView(QWidget):
    """
    MVP: Panda3D alohida oynada ko‘rsatadi.
    (Agar xohlasang keyingi bosqichda Qt widget ichiga embed qilamiz.)
    """
    def __init__(self, model_path: str, on_chat=None, on_quit=None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._app = self._get_app(model_path, on_chat, on_quit)
        if self._app is None:
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
