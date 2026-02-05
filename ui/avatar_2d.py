import glob
import os
from typing import Callable

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget


class Avatar2D(QWidget):
    """
    Lightweight 2D avatar meant to feel like a VTuber-style companion.
    Uses user-provided PNG sequences when available; falls back to procedural art.
    """

    def __init__(self, assets_dir: str, on_chat: Callable | None = None, on_quit: Callable | None = None) -> None:
        super().__init__()
        self._assets_dir = assets_dir
        self._on_chat = on_chat
        self._on_quit = on_quit
        self._state = "idle"
        self._frame_idx = 0
        self._canvas_size = QSize(500, 700)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setScaledContents(True)

        self._frames = self._build_frame_map()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self.setLayout(layout)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.set_state("idle")

    def sizeHint(self):
        return self._canvas_size

    def set_state(self, state: str) -> None:
        state = (state or "idle").lower()
        if state not in self._frames:
            state = "idle"
        self._state = state
        self._frame_idx = 0
        self._update_frame()
        self._timer.start(self._interval_for(state))

    def _next_frame(self) -> None:
        self._frame_idx = (self._frame_idx + 1) % max(len(self._frames.get(self._state, [])), 1)
        self._update_frame()

    def _update_frame(self) -> None:
        seq = self._frames.get(self._state) or self._frames.get("idle") or []
        if not seq:
            return
        frame = seq[self._frame_idx % len(seq)]
        self._label.setPixmap(frame)

    def _interval_for(self, state: str) -> int:
        if state == "speaking":
            return 80
        if state == "listening":
            return 120
        if state == "thinking":
            return 140
        if state == "error":
            return 220
        return 150  # idle

    # ---------- UI events ----------
    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._on_chat:
            self._on_chat()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        chat_action = menu.addAction("Toggle chat")
        quit_action = menu.addAction("Quit")
        chosen = menu.exec(event.globalPos())
        if chosen is chat_action and self._on_chat:
            self._on_chat()
        if chosen is quit_action and self._on_quit:
            self._on_quit()

    # ---------- Asset loading ----------
    def _build_frame_map(self) -> dict[str, list[QPixmap]]:
        frame_map = {}
        for state in ("idle", "listening", "thinking", "speaking", "error"):
            seq = self._load_sequence(state)
            if not seq:
                seq = self._generate_fallback(state)
            frame_map[state] = seq
        return frame_map

    def _load_sequence(self, state: str) -> list[QPixmap]:
        frames: list[QPixmap] = []
        folder = os.path.join(self._assets_dir, state)
        if os.path.isdir(folder):
            files = sorted(glob.glob(os.path.join(folder, "*.png")))
            for path in files:
                pm = QPixmap(path)
                if not pm.isNull():
                    frames.append(pm.scaled(self._canvas_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        fallback_png = os.path.join(self._assets_dir, f"{state}.png")
        if not frames and os.path.exists(fallback_png):
            pm = QPixmap(fallback_png)
            if not pm.isNull():
                frames.append(pm.scaled(self._canvas_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return frames

    # ---------- Procedural fallback ----------
    def _generate_fallback(self, state: str) -> list[QPixmap]:
        accent = {
            "idle": QColor("#8ad7ff"),
            "listening": QColor("#9dd2ff"),
            "thinking": QColor("#c9a8ff"),
            "speaking": QColor("#ff8ccf"),
            "error": QColor("#ff6b6b"),
        }.get(state, QColor("#8ad7ff"))

        frames = []
        if state == "speaking":
            mouths = ("soft", "open", "wide", "open")
            eyes = ("open", "open", "open", "smile")
        elif state == "listening":
            mouths = ("dot", "dot", "soft")
            eyes = ("focused", "open", "open")
        elif state == "thinking":
            mouths = ("dot", "soft", "dot")
            eyes = ("open", "blink", "open")
        elif state == "error":
            mouths = ("flat", "flat")
            eyes = ("closed", "closed")
        else:  # idle
            mouths = ("soft", "soft", "soft", "soft")
            eyes = ("open", "open", "blink", "open")

        for m, e in zip(mouths, eyes):
            frames.append(self._draw_face(accent, eye_state=e, mouth_state=m, overlay=state))
        return frames

    def _draw_face(self, accent: QColor, eye_state: str, mouth_state: str, overlay: str) -> QPixmap:
        w, h = self._canvas_size.width(), self._canvas_size.height()
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, accent.lighter(160))
        grad.setColorAt(0.45, accent)
        grad.setColorAt(1.0, accent.darker(170))
        painter.fillRect(0, 0, w, h, grad)

        halo_color = QColor(255, 255, 255, 90)
        painter.setBrush(halo_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(w // 2, h // 2 + 40), 240, 260)

        # Backdrop ring
        painter.setPen(QPen(QColor(255, 255, 255, 60), 8))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPoint(w // 2, h // 2 + 40), 230, 250)

        # Shoulders / hoodie
        torso_color = accent.darker(150)
        painter.setBrush(torso_color)
        torso = QPainterPath()
        torso.addRoundedRect(w // 2 - 140, h // 2 + 170, 280, 180, 60, 60)
        painter.drawPath(torso)
        painter.setBrush(accent.lighter(125))
        painter.drawEllipse(QPoint(w // 2, h // 2 + 210), 50, 32)
        # Hoodie strings
        painter.setPen(QPen(QColor(255, 255, 255, 210), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(w // 2 - 22, h // 2 + 180, w // 2 - 26, h // 2 + 240)
        painter.drawLine(w // 2 + 22, h // 2 + 180, w // 2 + 26, h // 2 + 240)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(w // 2 - 26, h // 2 + 244), 10, 8)
        painter.drawEllipse(QPoint(w // 2 + 26, h // 2 + 244), 10, 8)

        # Bunny ears
        ear_outer = QColor(247, 184, 220, 230)
        ear_inner = QColor(255, 214, 235, 230)
        for sign in (-1, 1):
            base_x = w // 2 + sign * 70
            painter.setBrush(ear_outer)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(base_x - 26, h // 2 - 220, 52, 190, 26, 26)
            painter.setBrush(ear_inner)
            painter.drawRoundedRect(base_x - 16, h // 2 - 210, 32, 160, 20, 20)

        # Hair base + bangs
        hair_main = QColor(247, 167, 206, 245)
        hair_shadow = QColor(229, 140, 184, 220)
        hair_hi = QColor(255, 205, 230, 190)
        hair_path = QPainterPath()
        hair_path.addRoundedRect(80, 70, w - 160, h - 240, 90, 90)
        painter.setBrush(hair_main)
        painter.setPen(Qt.NoPen)
        painter.drawPath(hair_path)
        painter.setBrush(hair_shadow)
        painter.drawEllipse(QPoint(w // 2 - 110, h // 2 - 30), 64, 82)
        painter.drawEllipse(QPoint(w // 2 + 110, h // 2 - 30), 64, 82)
        painter.setBrush(hair_hi)
        painter.drawEllipse(QPoint(w // 2, h // 2 - 100), 90, 60)
        # Bangs
        painter.setBrush(hair_main.darker(110))
        bangs = QPainterPath()
        bangs.moveTo(w // 2 - 140, h // 2 - 40)
        bangs.cubicTo(w // 2 - 40, h // 2 - 120, w // 2 + 40, h // 2 - 120, w // 2 + 140, h // 2 - 40)
        bangs.lineTo(w // 2 + 90, h // 2 + 40)
        bangs.cubicTo(w // 2 + 30, h // 2 - 10, w // 2 - 30, h // 2 - 10, w // 2 - 90, h // 2 + 40)
        bangs.closeSubpath()
        painter.drawPath(bangs)

        # Face
        face_color = QColor(255, 247, 245, 250)
        painter.setBrush(face_color)
        painter.drawEllipse(QPoint(w // 2, h // 2 + 30), 128, 170)

        # Blush
        cheek_color = QColor(255, 160, 200, 170)
        painter.setBrush(cheek_color)
        painter.drawEllipse(QPoint(w // 2 - 64, h // 2 + 34), 34, 18)
        painter.drawEllipse(QPoint(w // 2 + 64, h // 2 + 34), 34, 18)

        # Eyes (sclera + iris + pupil)
        eye_y = h // 2 - 4
        eye_dx = 70
        sclera = QColor(255, 255, 255, 255)
        iris = QColor(255, 188, 220, 240)
        iris_ring = QColor(235, 120, 180, 240)
        pupil = QColor(60, 40, 70, 255)
        highlight = QColor(255, 255, 255, 220)

        if eye_state in ("blink", "closed"):
            pen = QPen(pupil, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(w // 2 - eye_dx - 20, eye_y, w // 2 - eye_dx + 20, eye_y)
            painter.drawLine(w // 2 + eye_dx - 20, eye_y, w // 2 + eye_dx + 20, eye_y)
        else:
            for sign in (-1, 1):
                cx = w // 2 + sign * eye_dx
                painter.setBrush(sclera)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPoint(cx, eye_y), 26, 30)
                painter.setBrush(iris_ring)
                painter.drawEllipse(QPoint(cx, eye_y + 4), 20, 22)
                painter.setBrush(iris)
                painter.drawEllipse(QPoint(cx, eye_y + 6), 16, 18)
                painter.setBrush(pupil)
                painter.drawEllipse(QPoint(cx, eye_y + 10), 8, 10)
                painter.setBrush(highlight)
                painter.drawEllipse(QPoint(cx - 6, eye_y - 2), 5, 5)
                painter.drawEllipse(QPoint(cx + 4, eye_y + 6), 3, 3)
            if eye_state == "focused":
                brow_pen = QPen(pupil, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(brow_pen)
                painter.drawLine(w // 2 - eye_dx - 18, eye_y - 30, w // 2 - eye_dx + 22, eye_y - 20)
                painter.drawLine(w // 2 + eye_dx - 22, eye_y - 20, w // 2 + eye_dx + 18, eye_y - 30)
            elif eye_state == "smile":
                brow_pen = QPen(pupil, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(brow_pen)
                painter.drawArc(w // 2 - eye_dx - 26, eye_y - 12, 44, 22, 16 * 200, 16 * 120)
                painter.drawArc(w // 2 + eye_dx - 18, eye_y - 12, 44, 22, 16 * 220, 16 * 120)

        # Mouth
        mouth_pen = QPen(QColor(185, 45, 95), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(mouth_pen)
        mouth_y = h // 2 + 104
        if mouth_state == "dot":
            painter.drawPoint(w // 2, mouth_y)
        elif mouth_state == "flat":
            painter.drawLine(w // 2 - 20, mouth_y, w // 2 + 20, mouth_y)
        elif mouth_state == "open":
            painter.drawArc(w // 2 - 28, mouth_y - 10, 56, 32, 0, 16 * 180)
        elif mouth_state == "wide":
            painter.drawArc(w // 2 - 36, mouth_y - 14, 72, 36, 0, 16 * 180)
        else:  # soft / smile
            painter.drawArc(w // 2 - 24, mouth_y - 8, 48, 26, 0, 16 * 180)

        # Overlays per state
        if overlay == "thinking":
            painter.setBrush(QColor(255, 255, 255, 190))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPoint(w // 2 + 124, h // 2 - 130), 24, 24)
            painter.drawEllipse(QPoint(w // 2 + 150, h // 2 - 150), 14, 14)
        if overlay == "listening":
            painter.setPen(QPen(QColor(255, 255, 255, 210), 4))
            painter.drawArc(w // 2 - eye_dx - 48, eye_y - 38, 36, 48, 16 * 200, 16 * 120)
            painter.drawArc(w // 2 + eye_dx + 12, eye_y - 38, 36, 48, 16 * 200, 16 * 120)
        if overlay == "speaking":
            painter.setPen(QPen(QColor(255, 255, 255, 190), 4, Qt.DotLine))
            painter.drawArc(w // 2 + 90, mouth_y - 48, 70, 60, 16 * 260, 16 * 120)
        if overlay == "error":
            painter.setPen(QPen(QColor(255, 255, 255, 150), 3))
            painter.drawLine(w // 2 - 18, mouth_y - 22, w // 2 + 18, mouth_y + 14)
            painter.drawLine(w // 2 + 18, mouth_y - 22, w // 2 - 18, mouth_y + 14)

        painter.end()
        return pm
