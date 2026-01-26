import asyncio
import tempfile
import threading

import edge_tts
from playsound import playsound


class TTSPlayer:
    def __init__(self, voice: str) -> None:
        self._voice = voice
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        if not text or not text.strip():
            return
        thread = threading.Thread(target=self._run, args=(text,), daemon=True)
        thread.start()

    def _run(self, text: str) -> None:
        if not self._lock.acquire(blocking=False):
            return
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                path = f"{tmp_dir}\\tts.mp3"
                asyncio.run(self._synthesize(text, path))
                playsound(path)
        finally:
            self._lock.release()

    async def _synthesize(self, text: str, path: str) -> None:
        communicate = edge_tts.Communicate(text, voice=self._voice)
        await communicate.save(path)
