import os
import time
import random
import logging
from datetime import datetime


class MoodEngine:
    _MOODS = ("sleepy", "playful", "focused", "annoyed", "proud", "caring")

    def __init__(self) -> None:
        self._mood = "focused"
        self._last_change = time.time()

    def current(self) -> str:
        return self._mood

    def tick(self, now: float, silence_sec: float | None = None) -> None:
        # Time-of-day drift
        hour = datetime.fromtimestamp(now).hour
        if 0 <= hour < 4:
            self._set("sleepy", now)
        elif 22 <= hour <= 23:
            self._set("playful", now)
        elif 5 <= hour < 7:
            self._set("caring", now)
        elif 7 <= hour < 18 and silence_sec is not None and silence_sec > 1800:
            self._set("focused", now)

    def apply_event(self, event: str, now: float | None = None) -> None:
        now = now or time.time()
        if event == "user_input":
            self._set("focused", now)
        elif event == "long_focus":
            self._set("proud", now)
        elif event == "late_gaming":
            self._set("playful", now)
        elif event == "alarm":
            self._set("caring", now)

    def _set(self, mood: str, now: float) -> None:
        if mood not in self._MOODS:
            return
        if mood == self._mood and now - self._last_change < 600:
            return
        self._mood = mood
        self._last_change = now


class ProactiveEngine:
    def __init__(self) -> None:
        self._last = 0.0
        self._cooldown = 8 * 60  # seconds

    def maybe(self, now: float, silence_sec: float, mood: str) -> str | None:
        if silence_sec < 600:  # <10 minutes
            return None
        if now - self._last < self._cooldown:
            return None
        self._last = now
        hour = datetime.fromtimestamp(now).hour
        if hour >= 23 or hour < 3:
            return "You still awake? Come curl up and rest~"
        if 5 <= hour < 7:
            return "Morning already... want me to nudge you up?"
        if 19 <= hour <= 22 and mood == "playful":
            return "Game time? I?ll cheer quietly, promise."
        if silence_sec > 3600:
            return "You?re deep in focus, huh? I?m here when you need me."
        return "It?s quiet? need a hand or just vibes?"


class MemoryLogger:
    def __init__(self) -> None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        log_dir = os.path.join(base_dir, ".hana_logs")
        os.makedirs(log_dir, exist_ok=True)
        self._path = os.path.join(log_dir, "waifu.log")
        logging.basicConfig(level=logging.INFO, filename=self._path, filemode="a", format="%(asctime)s %(message)s")
        self._seen = set()

    def log(self, fact: str) -> None:
        fact = fact.strip()
        if not fact:
            return
        key = fact.lower()
        if key in self._seen:
            return
        self._seen.add(key)
        try:
            logging.info(f"memory: {fact}")
        except Exception:
            pass


class PersonaStyler:
    @staticmethod
    def style_tag(mood: str | None) -> str:
        mood = (mood or "").lower()
        mapping = {
            "sleepy": "sleepy",
            "playful": "teasing",
            "focused": "calm",
            "annoyed": "calm",
            "proud": "excited",
            "caring": "calm",
        }
        return mapping.get(mood, "calm")

    @staticmethod
    def soften(text: str) -> str:
        replacements = {
            "enabled": "on",
            "completed": "done",
            "executed": "done",
            "processing": "on it",
            "initialized": "ready",
            "request": "ask",
            "response": "reply",
        }
        out = text
        for k, v in replacements.items():
            out = out.replace(k, v)
            out = out.replace(k.capitalize(), v.capitalize())
        return out

    @staticmethod
    def style(text: str, mood: str, persona: str) -> str:
        if not text:
            return text
        persona = (persona or "waifu").lower()
        mood = (mood or "focused").lower()
        base = PersonaStyler.soften(text).strip()
        if len(base) > 140:
            base = base[:136].rstrip() + "?"
        prefix = ""
        suffix = ""
        if mood == "sleepy":
            prefix = "mmh? "
            suffix = " zzz"
        elif mood == "playful":
            suffix = "~"
        elif mood == "annoyed":
            prefix = "hey, "
        elif mood == "proud":
            prefix = "told you I got this? "
        elif mood == "caring":
            prefix = "hey love, "
        if persona in ("waifu", "companion", "girlfriend", "vtuber"):
            return f"{prefix}{base}{suffix}"
        return base


class WaifuLayer:
    def __init__(self, config) -> None:
        self._config = config
        self._mood = MoodEngine()
        self._proactive = ProactiveEngine()
        self._memory = MemoryLogger()

    def update_event(self, event: str, now: float | None = None) -> None:
        self._mood.apply_event(event, now)

    def tick(self, silence_sec: float, now: float | None = None) -> str | None:
        now = now or time.time()
        self._mood.tick(now, silence_sec)
        msg = self._proactive.maybe(now, silence_sec, self._mood.current())
        if msg:
            hour = datetime.fromtimestamp(now).hour
            if hour >= 23 or hour < 3:
                self._memory.log("User stays up late gaming or working.")
            elif 5 <= hour < 7:
                self._memory.log("User hears early alarms.")
            elif silence_sec > 3600:
                self._memory.log("User focuses quietly for long stretches.")
        return msg

    def filter_reply(self, text: str) -> str:
        return PersonaStyler.style(text, self._mood.current(), self._config.persona)

    def style_tag(self) -> str:
        return PersonaStyler.style_tag(self._mood.current())

    def idle_state(self) -> str:
        return "idle"

    def log_memory(self, fact: str) -> None:
        self._memory.log(fact)

    def mood(self) -> str:
        return self._mood.current()
