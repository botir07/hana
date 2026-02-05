import asyncio
import tempfile
import threading

import edge_tts
from playsound import playsound


class TTSPlayer:
    def __init__(self, voice: str) -> None:
        self._voice = voice
        self._lock = threading.Lock()

    def set_voice(self, voice: str) -> None:
        if voice:
            self._voice = voice

    def speak(self, text: str, style: str | None = None, on_done=None) -> None:
        if not text or not text.strip():
            return
        thread = threading.Thread(target=self._run, args=(text, style, on_done), daemon=True)
        thread.start()

    def _run(self, text: str, style: str | None, on_done) -> None:
        if not self._lock.acquire(blocking=False):
            return
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                path = f"{tmp_dir}\\tts.mp3"
                asyncio.run(self._synthesize(text, path, style))
                playsound(path)
        finally:
            self._lock.release()
            if callable(on_done):
                try:
                    on_done()
                except Exception:
                    pass

    async def _synthesize(self, text: str, path: str, style: str | None) -> None:
        payload, rate, pitch = self._build_payload(text, style)
        communicate = edge_tts.Communicate(payload, voice=self._voice, rate=rate, pitch=pitch)
        await communicate.save(path)

    def _build_payload(self, text: str, style: str | None) -> tuple[str, str, str]:
        if not style:
            return text, "+0%", "+0Hz"
        style = style.strip().lower()
        mapping = {
            "calm": {"rate": "-3%", "pitch": "-2%"},
            "teasing": {"rate": "+6%", "pitch": "+6%"},
            "sleepy": {"rate": "-12%", "pitch": "-8%"},
            "excited": {"rate": "+10%", "pitch": "+10%"},
        }
        rates = mapping.get(style, mapping["calm"])
        rate = rates["rate"]
        pitch = rates["pitch"]
        return text, rate, pitch
