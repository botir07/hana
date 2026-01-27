# ui/avatar_view.py
import os
import builtins
import ctypes
import math
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout

from direct.showbase.ShowBase import ShowBase
from direct.actor.Actor import Actor
from panda3d.core import (
    loadPrcFileData,
    Filename,
    WindowProperties,
    Material,
    GeomVertexReader,
    GeomVertexWriter,
    GeomVertexData,
    GeomVertexFormat,
    Geom,
    Point3,
)


_PANDA_APP = None


class _WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _WinRect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _PandaApp(ShowBase):
    _BOUNDS_LIMIT = 1e5

    def __init__(self, model_path: str, on_chat, on_quit):
        # Panda3D oynasini Qt ichida ishlatish uchun alohida window ochmaslikka harakat qilamiz
        model_dir = os.path.dirname(model_path)
        if model_dir:
            loadPrcFileData("", f"model-path {model_dir}")
            tex_dir = os.path.join(model_dir, "Textures")
            if os.path.isdir(tex_dir):
                loadPrcFileData("", f"model-path {tex_dir}")
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
        self._actor = None
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
        self._cam_height = 2.2
        self._cam_look_z = 1.2
        self._rbutton_down = False
        self._menu_lock_until = 0.0
        self._ctrl_down = False
        self._auto_walk = os.environ.get("HANA_AUTO_WALK", "1").strip().lower() not in ("0", "false", "no", "off")
        self._enable_limb_motion = os.environ.get("HANA_ANIMATE_LIMBS", "0").strip().lower() in ("1", "true", "yes", "on")
        self._force_static = os.environ.get("HANA_FORCE_STATIC", "1").strip().lower() not in ("0", "false", "no", "off")
        self._allow_unsafe_anim = os.environ.get("HANA_ALLOW_UNSAFE_ANIMATE", "0").strip().lower() in ("1", "true", "yes", "on")
        self._walk_target = None
        self._walk_speed = 320.0
        self._screen_margin = 20
        self._auto_walk_started = False
        self._last_step_time = time.monotonic()
        self._joint_anim = []

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
        self.cam.setPos(0, -self._cam_dist, self._cam_height)
        self.cam.lookAt(0, 0, self._cam_look_z)
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
        self.accept("mouse3", self._show_system_menu)
        self.accept("control", self._on_ctrl_down)
        self.accept("control-up", self._on_ctrl_up)

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
            WS_SYSMENU = 0x00080000
            LWA_COLORKEY = 0x00000001
            ex_style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            ex_style = (ex_style | WS_EX_LAYERED | WS_EX_TOOLWINDOW) & ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, ex_style)
            style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_STYLE)
            style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZE | WS_MAXIMIZEBOX)
            style |= WS_SYSMENU
            ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_STYLE, style)
            # Apply style changes so Windows creates a system menu.
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            ctypes.windll.user32.SetWindowPos(
                self._hwnd,
                0,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
            # Make magenta fully transparent; keep dark colors intact.
            ctypes.windll.user32.SetLayeredWindowAttributes(self._hwnd, 0x00FF00FF, 0, LWA_COLORKEY)
        except Exception:
            return

    def _ensure_window(self, task):
        if self._hwnd:
            self._position_window()
            self._start_auto_walk()
            return task.done
        self._hwnd_tries += 1
        self._set_topmost()
        if self._hwnd or self._hwnd_tries >= 15:
            self._position_window()
            self._start_auto_walk()
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

    def _get_work_area(self):
        rect = _WinRect()
        SPI_GETWORKAREA = 0x0030
        try:
            if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            return None
        return None

    def _start_auto_walk(self) -> None:
        if not self._auto_walk or self._auto_walk_started:
            return
        if not self._hwnd:
            return
        rect = self._get_window_rect()
        if not rect:
            return
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        work = self._get_work_area()
        if work:
            left, top, right, bottom = work
        else:
            right = ctypes.windll.user32.GetSystemMetrics(0)
            bottom = ctypes.windll.user32.GetSystemMetrics(1)
            left = 0
            top = 0
        target_x = max(left + self._screen_margin, right - width - self._screen_margin)
        target_y = max(top + self._screen_margin, bottom - height - self._screen_margin)
        self._walk_target = (target_x, target_y)
        self._auto_walk_started = True

    def _on_drag_start(self) -> None:
        self._dragging = True
        self._last_cursor = None

    def _on_drag_end(self) -> None:
        self._dragging = False
        self._last_cursor = None

    def _zoom_in(self) -> None:
        self._cam_dist = max(2.8, self._cam_dist - 0.4)
        self.cam.setPos(0, -self._cam_dist, self._cam_height)
        self.cam.lookAt(0, 0, self._cam_look_z)

    def _zoom_out(self) -> None:
        self._cam_dist = min(9.0, self._cam_dist + 0.4)
        self.cam.setPos(0, -self._cam_dist, self._cam_height)
        self.cam.lookAt(0, 0, self._cam_look_z)

    def load_model(self, model_path: str) -> bool:
        self._model_error = None
        if self.model:
            self.model.removeNode()
            self.model = None
        self._actor = None
        self._bad_skinning = False
        # If limb animation requested, prefer Actor even if static was forced.
        use_force_static = self._force_static and not self._enable_limb_motion
        if os.path.exists(model_path):
            if model_path.lower().endswith((".gltf", ".glb")):
                try:
                    import gltf  # noqa: F401
                except Exception as exc:
                    self._model_error = f"panda3d-gltf import failed: {exc}"
                    return False
            p = Filename.fromOsSpecific(model_path)
            actor = None
            anims = self._find_anims(model_path)
            if not use_force_static:
                if anims:
                    try:
                        actor = Actor(p, anims)
                    except Exception as exc:
                        print(f"[HANA] Actor load with anims failed: {exc}")
                        actor = None
                if actor is None:
                    try:
                        actor = Actor(p)
                    except Exception as exc:
                        print(f"[HANA] Actor load failed: {exc}")
                        actor = None
            if actor:
                if actor.getAnimNames():
                    anim_name = actor.getAnimNames()[0]
                    actor.loop(anim_name)
                self._actor = actor
                self.model = actor
                print(f"[HANA] Actor mode enabled. joints={len(actor.getJoints())}")
            else:
                self.model = self.loader.loadModel(p)
                self._actor = None
                if not use_force_static and self._enable_limb_motion:
                    print("[HANA] Limb animation requested but Actor unavailable; using static model.")
            if not self.model or self.model.isEmpty():
                self.model = None
                self._model_error = "Model load failed. Check the file and texture paths."
                return False
            self.model.reparentTo(self.render)
            self.model.setHpr(0, 0, 0)
            self.model.setTwoSided(True)
            self.model.setShaderAuto()
            if use_force_static:
                print("[HANA] Force static ON -> stripping skinning.")
                self._strip_skinning()
            else:
                self._setup_joint_motion()
                if self._actor is None:
                    self._strip_skinning()
                elif not self._joint_anim:
                    print("[HANA] Actor loaded but no target joints found; freezing to static.")
                    self._freeze_to_static()

            # Detect exploded skinning and fall back to static if needed.
            bounds = self._compute_vertex_bounds()
            if bounds and self._bounds_ok(bounds):
                sz = bounds[1] - bounds[0]
                max_dim = max(sz.x, sz.y, sz.z)
                print(f"[HANA] Bounds after load: {bounds[0]} -> {bounds[1]} (max_dim={max_dim:.2f})")
                # Human-sized sanity: if exploded far beyond normal, treat as bad skinning unless user allows unsafe.
                if not self._allow_unsafe_anim and (max_dim > 30.0 or max_dim < 0.05):
                    print("[HANA] Bounds look wrong (size sanity failed); forcing static fallback.")
                    self._bad_skinning = True
            else:
                print("[HANA] Bounds invalid after load; forcing static fallback.")
                self._bad_skinning = True
            if self._actor and (self._bad_skinning or not self._bounds_ok(bounds)):
                if self._allow_unsafe_anim:
                    print("[HANA] Bounds failed sanity but unsafe animate is allowed; keeping Actor.")
                else:
                    self._freeze_to_static()
                    self._strip_skinning()
                    self._enable_limb_motion = False
                    print("[HANA] Skinning looked broken; reverted to static mesh and disabled limb motion.")
            self._apply_material()
            self._maybe_fix_axis()
            self._fit_model()
            return True
        self._model_error = "Model file not found."
        return False

    def _freeze_to_static(self) -> None:
        if not self._actor:
            return
        static_root = self.render.attachNewNode("static_model")
        try:
            for np in self._actor.findAllMatches("**/+GeomNode"):
                np.copyTo(static_root)
        except Exception:
            static_root.removeNode()
            return
        self._actor.detachNode()
        self.model = static_root
        self._actor = None
        self._joint_anim = []
        # Remove leftover skinning columns to avoid bogus joint transforms.
        self._strip_skinning()

    def _strip_skinning(self) -> None:
        if not self.model:
            return
        try:
            fmt = GeomVertexFormat.getV3n3c4t2()
            for np in self.model.findAllMatches("**/+GeomNode"):
                geom_node = np.node()
                for i in range(geom_node.getNumGeoms()):
                    geom = geom_node.modifyGeom(i)
                    vdata = geom.getVertexData()
                    if not vdata.hasColumn("transform_blend"):
                        continue
                    new_vdata = GeomVertexData(vdata.getName(), fmt, Geom.UHStatic)
                    new_vdata.setNumRows(vdata.getNumRows())

                    vr_v = GeomVertexReader(vdata, "vertex")
                    vr_n = GeomVertexReader(vdata, "normal") if vdata.hasColumn("normal") else None
                    vr_c = GeomVertexReader(vdata, "color") if vdata.hasColumn("color") else None
                    vr_t = GeomVertexReader(vdata, "texcoord") if vdata.hasColumn("texcoord") else None

                    vw_v = GeomVertexWriter(new_vdata, "vertex")
                    vw_n = GeomVertexWriter(new_vdata, "normal")
                    vw_c = GeomVertexWriter(new_vdata, "color")
                    vw_t = GeomVertexWriter(new_vdata, "texcoord")

                    for _ in range(vdata.getNumRows()):
                        vw_v.addData3f(vr_v.getData3f())
                        if vr_n and not vr_n.isAtEnd():
                            vw_n.addData3f(vr_n.getData3f())
                        else:
                            vw_n.addData3f(0, 0, 1)
                        if vr_c and not vr_c.isAtEnd():
                            vw_c.addData4f(vr_c.getData4f())
                        else:
                            vw_c.addData4f(1, 1, 1, 1)
                        if vr_t and not vr_t.isAtEnd():
                            t = vr_t.getData3f()
                            vw_t.addData2f(t.x, t.y)
                        else:
                            vw_t.addData2f(0, 0)

                    geom.setVertexData(new_vdata)
        except Exception:
            return

    def _setup_joint_motion(self) -> None:
        self._joint_anim = []
        if not self._enable_limb_motion or not self._actor:
            return
        joints = []
        try:
            if hasattr(self._actor, "getJoints"):
                joints = list(self._actor.getJoints())
        except Exception:
            joints = []
        if not joints:
            return
        print(f"[HANA] Joints available: {len(joints)}")
        picked = set()
        for joint in joints:
            name = joint.getName()
            kind, side = self._classify_joint(name)
            if not kind:
                continue
            key = (kind, side)
            if key in picked:
                continue
            try:
                ctrl = self._actor.controlJoint(None, "modelRoot", name)
            except Exception:
                ctrl = None
            if not ctrl:
                continue
            picked.add(key)
            self._joint_anim.append(
                {
                    "node": ctrl,
                    "base": ctrl.getHpr(),
                    "kind": kind,
                    "side": side,
                }
            )
            if len(self._joint_anim) >= 12:
                break
        print(f"[HANA] Joint motion targets: {len(self._joint_anim)} -> {[j['node'].getName() for j in self._joint_anim]}")

    def _classify_joint(self, name: str):
        lower = name.lower()
        if "upperarm" in lower or ("arm" in lower and "fore" not in lower and "hand" not in lower):
            kind = "arm"
        elif "forearm" in lower or "lowerarm" in lower:
            kind = "forearm"
        elif "hand" in lower or "wrist" in lower:
            kind = "hand"
        elif "thigh" in lower or "upleg" in lower:
            kind = "thigh"
        elif "calf" in lower or "lowerleg" in lower or ("leg" in lower and "upleg" not in lower):
            kind = "calf"
        elif "foot" in lower or "ankle" in lower:
            kind = "foot"
        elif "spine" in lower:
            kind = "spine"
        elif "shoulder" in lower or "clavicle" in lower:
            kind = "shoulder"
        else:
            return None, None
        side = self._detect_side(lower)
        return kind, side

    def _detect_side(self, lower: str):
        if "left" in lower or lower.endswith(".l") or lower.endswith("_l") or "_l" in lower or "l_" in lower:
            return "left"
        if "right" in lower or lower.endswith(".r") or lower.endswith("_r") or "_r" in lower or "r_" in lower:
            return "right"
        for kw in ("arm", "hand", "leg", "thigh", "calf", "foot", "shoulder", "clav"):
            if f"l{kw}" in lower or f"{kw}l" in lower:
                return "left"
            if f"r{kw}" in lower or f"{kw}r" in lower:
                return "right"
        return None

    def _maybe_fix_axis(self) -> None:
        bounds = self._compute_vertex_bounds()
        if not bounds:
            return
        min_pt, max_pt = bounds
        size = max_pt - min_pt
        if size.y > size.z * 1.6 and size.y > size.x * 1.2:
            self.model.setP(-90)

    def _find_anims(self, model_path: str) -> dict:
        model_dir = os.path.dirname(model_path)
        if not model_dir or not os.path.isdir(model_dir):
            return {}
        base_name = os.path.basename(model_path).lower()
        candidates = []
        try:
            for name in os.listdir(model_dir):
                if not name.lower().endswith(".fbx"):
                    continue
                if name.lower() == base_name:
                    continue
                candidates.append(name)
        except Exception:
            return {}
        if not candidates:
            return {}

        def _score(name: str) -> tuple:
            lower = name.lower()
            return (
                "walk" not in lower,
                "run" not in lower,
                "idle" not in lower,
                len(lower),
            )

        candidates = sorted(candidates, key=_score)
        anim_name = candidates[0]
        return {"walk": os.path.join(model_dir, anim_name)}

    def _fit_model(self) -> None:
        if not self.model:
            return
        bounds = self.model.getTightBounds()
        if not self._bounds_ok(bounds):
            bounds = self._compute_vertex_bounds()
        if not bounds:
            self.model.setScale(1.0)
            self.model.setPos(0, 0, 0)
            self._base_z = 0.0
            return
        min_pt, max_pt = bounds
        size = max_pt - min_pt
        max_dim = max(size.x, size.y, size.z, 1.0)
        scale = 2.0 / max_dim
        center = (min_pt + max_pt) * 0.5
        self.model.setScale(scale)
        self._base_z = -center.z * scale + 0.6
        self.model.setPos(-center.x * scale, -center.y * scale, self._base_z)
        world_bounds = self._compute_vertex_bounds()
        if world_bounds:
            self._frame_camera(world_bounds)
        else:
            self._frame_camera((min_pt * scale, max_pt * scale))

    def _frame_camera(self, bounds) -> None:
        min_pt, max_pt = bounds
        size = max_pt - min_pt
        max_dim = max(size.x, size.y, size.z)
        if not math.isfinite(max_dim) or max_dim <= 0:
            return
        radius = max_dim * 0.5
        center = (min_pt + max_pt) * 0.5
        self._cam_dist = max(3.0, radius * 3.0)
        self._cam_look_z = center.z + radius * 0.1
        self._cam_height = center.z + radius * 0.35
        self.cam.setPos(0, -self._cam_dist, self._cam_height)
        self.cam.lookAt(0, 0, self._cam_look_z)
        lens = self.cam.node().getLens()
        near = max(0.01, self._cam_dist * 0.03)
        far = max(50.0, self._cam_dist * 40.0)
        lens.setNearFar(near, far)

    def _bounds_ok(self, bounds) -> bool:
        if not bounds or bounds[0] is None or bounds[1] is None:
            return False
        min_pt, max_pt = bounds
        if not self._point_ok(min_pt) or not self._point_ok(max_pt):
            return False
        size = max_pt - min_pt
        max_dim = max(size.x, size.y, size.z)
        if not math.isfinite(max_dim) or max_dim <= 0 or max_dim > self._BOUNDS_LIMIT:
            return False
        return True

    def _point_ok(self, point) -> bool:
        return (
            math.isfinite(point.x)
            and math.isfinite(point.y)
            and math.isfinite(point.z)
            and abs(point.x) <= self._BOUNDS_LIMIT
            and abs(point.y) <= self._BOUNDS_LIMIT
            and abs(point.z) <= self._BOUNDS_LIMIT
        )

    def _compute_vertex_bounds(self):
        if not self.model:
            return None
        limit = self._BOUNDS_LIMIT
        min_x = float("inf")
        min_y = float("inf")
        min_z = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        max_z = float("-inf")
        count = 0
        for np in self.model.findAllMatches("**/+GeomNode"):
            geom_node = np.node()
            net_mat = np.getNetTransform().getMat()
            use_mat = not net_mat.isIdentity()
            for i in range(geom_node.getNumGeoms()):
                geom = geom_node.getGeom(i)
                vdata = geom.getVertexData()
                if not vdata:
                    continue
                reader = GeomVertexReader(vdata, "vertex")
                while not reader.isAtEnd():
                    v = reader.getData3f()
                    if use_mat:
                        v = net_mat.xformPoint(v)
                    x = float(v.x)
                    y = float(v.y)
                    z = float(v.z)
                    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                        continue
                    if abs(x) > limit or abs(y) > limit or abs(z) > limit:
                        continue
                    count += 1
                    if x < min_x:
                        min_x = x
                    if y < min_y:
                        min_y = y
                    if z < min_z:
                        min_z = z
                    if x > max_x:
                        max_x = x
                    if y > max_y:
                        max_y = y
                    if z > max_z:
                        max_z = z
        if count == 0:
            return None
        return Point3(min_x, min_y, min_z), Point3(max_x, max_y, max_z)

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
        if not self._hwnd:
            self._update_hwnd()
        if not self._hwnd:
            return
        VK_RBUTTON = 0x02
        state = ctypes.windll.user32.GetAsyncKeyState(VK_RBUTTON)
        down = (state & 0x8000) != 0
        if down and not self._rbutton_down:
            rect = self._get_window_rect()
            pos = self._get_cursor_pos()
            if rect and pos:
                left, top, right, bottom = rect
                if left <= pos[0] <= right and top <= pos[1] <= bottom:
                    self._show_system_menu()
        self._rbutton_down = down

    def step(self):
        now = time.monotonic()
        dt = max(0.0, now - self._last_step_time)
        self._last_step_time = now
        self._poll_right_click()
        if self._auto_walk and not self._auto_walk_started:
            self._start_auto_walk()
        self._advance_walk(dt)
        self._animate_joints(now, walking=self._walk_target is not None)
        if self.model:
            self.tilt = (self.tilt + 2.0) % 360.0
            if self._dragging:
                pos = self._get_cursor_pos()
                if pos:
                    if self._last_cursor is not None:
                        dx = pos[0] - self._last_cursor[0]
                        dy = pos[1] - self._last_cursor[1]
                        self._current_h -= dx * 0.15
                        self._current_p -= dy * 0.12
                        self._current_p = max(-40.0, min(40.0, self._current_p))
                    self._last_cursor = pos
            else:
                offset = self._get_cursor_offset()
                if offset:
                    dx, dy = offset
                    target_h = dx * self._max_heading
                    target_p = dy * self._max_pitch
                else:
                    target_h = 0.0
                    target_p = 0.0
                self._current_h += (target_h - self._current_h) * self._look_smooth
                self._current_p += (target_p - self._current_p) * self._look_smooth
            self.model.setH(self._current_h)
            self.model.setP(self._current_p + 2.0 * math.sin(self.tilt * 0.0174533))
            bob = self._bob_amp
            if self._walk_target is not None:
                bob = max(bob, 0.14)
            self.model.setZ(self._base_z + bob * math.sin(self.tilt * 0.0174533))

    def _advance_walk(self, dt: float) -> None:
        if not self._walk_target or not self._hwnd or dt <= 0:
            return
        rect = self._get_window_rect()
        if not rect:
            return
        cur_x, cur_y = rect[0], rect[1]
        target_x, target_y = self._walk_target
        dx = target_x - cur_x
        dy = target_y - cur_y
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            self._walk_target = None
            return
        step = self._walk_speed * dt
        if step > dist:
            step = dist
        nx = int(cur_x + dx / dist * step)
        ny = int(cur_y + dy / dist * step)
        try:
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(self._hwnd, -1, nx, ny, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            return

    def _animate_joints(self, t: float, walking: bool = False) -> None:
        if not self._joint_anim:
            return
        speed = 6.0 if walking else 2.2
        phase = t * speed
        for item in self._joint_anim:
            node = item["node"]
            base = item["base"]
            kind = item["kind"]
            side = item["side"]
            side_mult = 1
            if side == "left":
                side_mult = -1
            elif side == "right":
                side_mult = 1
            if kind == "arm":
                amp = 22.0 if walking else 10.0
                pitch = math.sin(phase) * amp * side_mult
            elif kind == "forearm":
                amp = 14.0 if walking else 6.0
                pitch = math.sin(phase + 0.6) * amp * side_mult
            elif kind == "hand":
                amp = 8.0 if walking else 4.0
                pitch = math.sin(phase + 1.0) * amp * side_mult
            elif kind == "thigh":
                amp = 18.0 if walking else 6.0
                pitch = math.sin(phase + math.pi) * amp * side_mult
            elif kind == "calf":
                amp = 12.0 if walking else 4.0
                pitch = math.sin(phase + math.pi + 0.5) * amp * side_mult
            elif kind == "foot":
                amp = 6.0 if walking else 2.0
                pitch = math.sin(phase + math.pi + 1.0) * amp * side_mult
            elif kind == "spine":
                amp = 4.0 if walking else 2.0
                pitch = math.sin(phase * 0.5) * amp
            elif kind == "shoulder":
                amp = 6.0 if walking else 3.0
                pitch = math.sin(phase) * amp * (side_mult or 1)
            else:
                continue
            node.setHpr(base.x, base.y + pitch, base.z)

    def _toggle_menu(self) -> None:
        if self._menu:
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
            command=self._on_menu_chat,
        )
        DirectButton(
            parent=self._menu,
            text="Exit",
            scale=0.05,
            pos=(100, 0, -70),
            frameColor=(0.15, 0.15, 0.18, 1.0),
            command=self._on_menu_exit,
        )

    def _maybe_toggle_menu(self) -> None:
        now = time.monotonic()
        if now < self._menu_lock_until:
            return
        self._menu_lock_until = now + 0.2
        self._toggle_menu()

    def _show_system_menu(self) -> None:
        if not self._ctrl_down:
            return
        now = time.monotonic()
        if now < self._menu_lock_until:
            return
        self._menu_lock_until = now + 0.2
        if not self._hwnd:
            self._update_hwnd()
        if not self._hwnd:
            return
        pos = self._get_cursor_pos()
        if not pos:
            return
        x, y = pos
        try:
            hmenu = ctypes.windll.user32.GetSystemMenu(self._hwnd, False)
            menu_owned = False
            if not hmenu:
                # Build a minimal system-style menu when Windows doesn't provide one.
                hmenu = ctypes.windll.user32.CreatePopupMenu()
                if not hmenu:
                    return
                menu_owned = True
                MF_STRING = 0x0000
                MF_SEPARATOR = 0x0800
                SC_RESTORE = 0xF120
                SC_MOVE = 0xF010
                SC_SIZE = 0xF000
                SC_MINIMIZE = 0xF020
                SC_MAXIMIZE = 0xF030
                SC_CLOSE = 0xF060
                ID_CHAT = 0x1001
                ID_EXIT = 0x1002
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, SC_RESTORE, "Restore")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, SC_MOVE, "Move")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, SC_SIZE, "Size")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, SC_MINIMIZE, "Minimize")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, SC_MAXIMIZE, "Maximize")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, ID_CHAT, "Chat")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, ID_EXIT, "Exit")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, SC_CLOSE, "Close")
            else:
                MF_STRING = 0x0000
                MF_SEPARATOR = 0x0800
                ID_CHAT = 0x1001
                ID_EXIT = 0x1002
                ctypes.windll.user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, ID_CHAT, "Chat")
                ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, ID_EXIT, "Exit")
            TPM_LEFTALIGN = 0x0000
            TPM_RETURNCMD = 0x0100
            cmd = ctypes.windll.user32.TrackPopupMenu(
                hmenu,
                TPM_LEFTALIGN | TPM_RETURNCMD,
                x,
                y,
                0,
                self._hwnd,
                None,
            )
            if cmd == ID_CHAT:
                self._on_chat()
            elif cmd == ID_EXIT:
                self._on_quit()
            elif cmd:
                WM_SYSCOMMAND = 0x0112
                ctypes.windll.user32.SendMessageW(self._hwnd, WM_SYSCOMMAND, cmd, 0)
            if menu_owned:
                ctypes.windll.user32.DestroyMenu(hmenu)
        except Exception:
            return

    def _on_ctrl_down(self) -> None:
        self._ctrl_down = True

    def _on_ctrl_up(self) -> None:
        self._ctrl_down = False

    def _close_menu(self) -> None:
        if self._menu:
            self._menu.destroy()
            self._menu = None

    def _on_menu_chat(self) -> None:
        self._close_menu()
        self._on_chat()

    def _on_menu_exit(self) -> None:
        self._close_menu()
        self._on_quit()

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
