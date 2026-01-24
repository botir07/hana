import json
import os
import re
import sys
import urllib.error
import urllib.request

try:
    from core.config import Config
except ModuleNotFoundError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from core.config import Config


class Agent:
    def __init__(self) -> None:
        self._config = Config()

    def has_api_key(self) -> bool:
        return bool(self._config.api_key)

    def set_api_key(self, api_key: str) -> None:
        self._config.save_api_key(api_key)
        self._config.api_key = api_key

    def set_model(self, model: str) -> None:
        self._config.save_model(model)
        self._config.model = model

    def process_text(self, text: str) -> dict:
        if not self._config.api_key:
            return {"type": "reply", "message": "OPENROUTER_API_KEY is not set."}

        payload = {
            "model": self._config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are HANA, a local desktop assistant. "
                        "Return only strict JSON. "
                        "Schema: {\"type\":\"reply\",\"message\":\"...\"} "
                        "or {\"type\":\"action\",\"action\":\"file.open|file.rename|file.move|file.delete|file.create_folder|system.launch|system.open_path|system.open_url\","
                        "\"args\":{...},\"message\":\"...\"}. "
                        "Use system.open_url with {\"url\":\"https://...\"} to open sites "
                        "or search with {\"query\":\"...\"}."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
        }

        req = urllib.request.Request(
            self._config.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = ""
            if exc.code == 401:
                return {
                    "type": "reply",
                    "message": "Unauthorized: check your OpenRouter API key.",
                }
            if exc.code == 402:
                return {
                    "type": "reply",
                    "message": "Payment required: check OpenRouter credits or model access.",
                }
            if exc.code == 404:
                return {
                    "type": "reply",
                    "message": f"HTTP 404: model not found ({self._config.model}). Set a valid OpenRouter model.",
                }
            detail = f"HTTP error: {exc.code}"
            if error_body:
                detail = f"{detail} - {error_body}"
            return {"type": "reply", "message": detail}

        content = data["choices"][0]["message"]["content"]
        parsed = self._parse_json(content)
        if parsed is None:
            return {"type": "reply", "message": "LLM returned invalid JSON."}

        if not isinstance(parsed, dict) or "type" not in parsed:
            return {"type": "reply", "message": "LLM returned unexpected JSON."}

        return parsed

    def _parse_json(self, content: str) -> dict | None:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                return None

        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        snippet = content[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None
