import os


class Config:
    def __init__(self) -> None:
        self._load_env()
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        self.api_url = os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        self.language = os.environ.get("AIRI_LANGUAGE", "english")
        self.tts_voice = os.environ.get("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural")
        self.db_path = os.path.join(base_dir, "hana.db")
        self.trash_dir = os.path.join(base_dir, ".hana_trash")

    def save_api_key(self, api_key: str) -> None:
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="ascii") as handle:
                lines = [line.rstrip("\n") for line in handle]
        updated = False
        for idx, line in enumerate(lines):
            if line.startswith("OPENROUTER_API_KEY="):
                lines[idx] = f"OPENROUTER_API_KEY={api_key}"
                updated = True
                break
        if not updated:
            lines.append(f"OPENROUTER_API_KEY={api_key}")
        with open(env_path, "w", encoding="ascii") as handle:
            handle.write("\n".join(lines) + "\n")
        os.environ["OPENROUTER_API_KEY"] = api_key

    def save_model(self, model: str) -> None:
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="ascii") as handle:
                lines = [line.rstrip("\n") for line in handle]
        updated = False
        for idx, line in enumerate(lines):
            if line.startswith("OPENROUTER_MODEL="):
                lines[idx] = f"OPENROUTER_MODEL={model}"
                updated = True
                break
        if not updated:
            lines.append(f"OPENROUTER_MODEL={model}")
        with open(env_path, "w", encoding="ascii") as handle:
            handle.write("\n".join(lines) + "\n")
        os.environ["OPENROUTER_MODEL"] = model

    def save_language(self, language: str) -> None:
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="ascii") as handle:
                lines = [line.rstrip("\n") for line in handle]
        updated = False
        for idx, line in enumerate(lines):
            if line.startswith("AIRI_LANGUAGE="):
                lines[idx] = f"AIRI_LANGUAGE={language}"
                updated = True
                break
        if not updated:
            lines.append(f"AIRI_LANGUAGE={language}")
        with open(env_path, "w", encoding="ascii") as handle:
            handle.write("\n".join(lines) + "\n")
        os.environ["AIRI_LANGUAGE"] = language

    @staticmethod
    def default_voice(language: str) -> str:
        mapping = {
            "english": "en-US-JennyNeural",
            "russian": "ru-RU-SvetlanaNeural",
            "uzbek": "uz-UZ-MadinaNeural",
        }
        return mapping.get(language, "ru-RU-SvetlanaNeural")

    def _load_env(self) -> None:
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        if not os.path.exists(env_path):
            return
        with open(env_path, "r", encoding="ascii") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
