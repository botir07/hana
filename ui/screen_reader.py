from typing import Optional
from pathlib import Path
import shutil

from PySide6.QtCore import QThread, Signal


class ScreenReader(QThread):
    """Capture the primary monitor and emit OCR text in the background."""

    text_ready = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        interval_ms: int = 2000,
        language: str = "eng",
        min_confidence: int = 65,
        max_chars: int = 800,
    ) -> None:
        super().__init__()
        self._interval_ms = max(200, int(interval_ms))
        self._language = language or "eng"
        self._min_confidence = max(0, min_confidence)
        self._max_chars = max_chars
        self._last_text: Optional[str] = None

    def run(self) -> None:
        try:
            import mss  # type: ignore
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore
            from pytesseract import Output  # type: ignore
            # If Tesseract isn't on PATH, try the default Windows install location
            if shutil.which("tesseract") is None:
                win_tesseract = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
                if win_tesseract.exists():
                    pytesseract.pytesseract.tesseract_cmd = str(win_tesseract)
        except Exception as exc:  # pragma: no cover - import/runtime environment
            self.error.emit(f"Missing dependency: {exc}")
            return

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary display
                while not self.isInterruptionRequested():
                    try:
                        grab = sct.grab(monitor)
                        img = Image.frombytes("RGB", grab.size, grab.bgra, "raw", "BGRX").convert("L")
                        text = self._extract_text(pytesseract, Output, img)
                        if text and text != self._last_text:
                            self._last_text = text
                            self.text_ready.emit(text)
                    except pytesseract.TesseractNotFoundError:
                        self.error.emit(
                            "Tesseract OCR not found. Install it and ensure the `tesseract` executable is on PATH."
                        )
                        return
                    except Exception as exc:
                        self.error.emit(str(exc))
                        return
                    self.msleep(self._interval_ms)
        except Exception as exc:  # pragma: no cover
            self.error.emit(str(exc))

    def _extract_text(self, pytesseract, Output, img) -> str:
        """Run OCR and drop low-confidence noise before emitting."""
        data = pytesseract.image_to_data(img, lang=self._language, output_type=Output.DICT)
        texts: list[str] = []
        current_line: list[str] = []
        last_line_no: Optional[int] = None

        for word, conf, line_no in zip(
            data.get("text", []),
            data.get("conf", []),
            data.get("line_num", []),
        ):
            try:
                conf_val = float(conf)
            except (TypeError, ValueError):
                continue
            if conf_val < self._min_confidence:
                continue
            word = (word or "").strip()
            if not word:
                continue
            if last_line_no is None or line_no == last_line_no:
                current_line.append(word)
            else:
                texts.append(" ".join(current_line))
                current_line = [word]
            last_line_no = line_no

        if current_line:
            texts.append(" ".join(current_line))

        joined = "\n".join(texts).strip()
        if len(joined) > self._max_chars:
            truncated = joined[: self._max_chars]
            # Avoid cutting in the middle of a word for smoother TTS.
            if " " in truncated:
                truncated = truncated.rsplit(" ", 1)[0]
            joined = truncated.strip()
        return joined
