import json
import os
import re
import sys
import time
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
        self._free_models_cache = []
        self._free_models_cached_at = 0.0
        self._url_re = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)

    def has_api_key(self) -> bool:
        return bool(self._config.api_key)

    def set_api_key(self, api_key: str) -> None:
        self._config.save_api_key(api_key)
        self._config.api_key = api_key

    def set_model(self, model: str) -> None:
        self._config.save_model(model)
        self._config.model = model

    def set_language(self, language: str) -> None:
        self._config.save_language(language)
        self._config.language = language

    def process_text(self, text: str) -> dict:
        if not self._config.api_key:
            return {"type": "reply", "message": "OPENROUTER_API_KEY is not set."}

        quick_action = self._rule_based_action(text)
        if quick_action:
            return quick_action

        language_instruction = self._language_instruction()
        system_prompt = (
            "You are AIRI, an advanced real-time AI assistant and autonomous agent. "
            "Core purpose: interact naturally through text, understand intent, and use tools safely. "
            "Personality: calm, intelligent, friendly but professional, short and clear by default, "
            "match user tone, never robotic. "
            f"{language_instruction} "
            "Thinking model: decide normal response vs action vs confirmation; validate safety; "
            "choose tool; execute; respond with result. Do not reveal internal reasoning unless asked. "
            "Memory: remember user preferences and context during the session. "
            "Action format when needed: return ONLY JSON with keys "
            "{\"type\":\"action\",\"action\":\"...\",\"args\":{...},\"message\":\"...\"}. "
            "Allowed actions: file.open, file.rename, file.move, file.delete, file.create_folder, "
            "system.launch, system.open_path, system.open_url. "
            "You are allowed to open apps, folders, and websites. "
            "When the user asks to open or launch something, ALWAYS return an action JSON. "
            "Use system.open_url with {\"url\":\"https://...\"} or {\"query\":\"...\"} for websites. "
            "Use system.launch with {\"target\":\"app_name\"} to open apps (Telegram, Explorer, etc.). "
            "If the user asks to play a song/video on YouTube and gives no URL, "
            "use system.open_url with {\"provider\":\"youtube\",\"query\":\"...\",\"play\":true}. "
            "For replies: {\"type\":\"reply\",\"message\":\"...\"}. "
            "Use system.open_url with {\"url\":\"https://...\"} to open sites or "
            "{\"query\":\"...\"} to search. "
            "Dangerous actions require confirmation."
        )

        models = self._get_free_models()
        if self._config.model and self._config.model not in models:
            models = [self._config.model] + models
        last_error = None

        for model in models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
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
                    content = data["choices"][0]["message"]["content"]
                    parsed = self._parse_json(content)
                    normalized = self._normalize_response(content, parsed)
                    if normalized.get("type") == "reply":
                        fallback = self._rule_based_action(text)
                        if fallback:
                            return fallback
                    return normalized
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
                if exc.code in (402, 404, 429):
                    last_error = f"HTTP {exc.code}: {model}"
                    continue
                detail = f"HTTP error: {exc.code}"
                if error_body:
                    detail = f"{detail} - {error_body}"
                return {"type": "reply", "message": detail}
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = f"Network error: {exc}"
                continue
            except Exception as exc:
                last_error = f"Unexpected error: {exc}"
                continue

        fallback = self._rule_based_action(text)
        if fallback:
            return fallback
        if last_error:
            return {"type": "reply", "message": f"All free models failed. Last error: {last_error}"}
        return {"type": "reply", "message": "Failed to contact OpenRouter."}

    def _get_free_models(self) -> list[str]:
        now = time.monotonic()
        if self._free_models_cache and now - self._free_models_cached_at < 600:
            return list(self._free_models_cache)

        url = "https://openrouter.ai/api/v1/models"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return [self._config.model] if self._config.model else []

        models = []
        for item in data.get("data", []):
            model_id = item.get("id", "")
            pricing = item.get("pricing", {}) or {}
            prompt_price = pricing.get("prompt")
            completion_price = pricing.get("completion")
            if prompt_price != "0" or completion_price != "0":
                continue
            architecture = item.get("architecture", {}) or {}
            modality = architecture.get("modality", "")
            output_modalities = architecture.get("output_modalities", []) or []
            if modality and "text->text" not in modality and "text" not in output_modalities:
                continue
            models.append(model_id)

        def _score(model_id: str) -> tuple:
            lower = model_id.lower()
            return (
                ":free" not in lower,
                "instruct" not in lower and "chat" not in lower,
                len(model_id),
            )

        models = sorted(set(models), key=_score)
        if not models and self._config.model:
            return [self._config.model]

        self._free_models_cache = models
        self._free_models_cached_at = now
        return list(models)

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

    def _normalize_response(self, content: str, parsed: object) -> dict:
        if isinstance(parsed, dict):
            response_type = parsed.get("type")
            if response_type in ("reply", "action"):
                if response_type == "action" and "action" not in parsed:
                    return {"type": "reply", "message": str(parsed.get("message", ""))}
                if response_type == "action" and not isinstance(parsed.get("args"), dict):
                    parsed["args"] = {}
                if response_type == "action":
                    parsed["action"] = self._normalize_action_name(str(parsed.get("action", "")))
                return parsed
            if "action" in parsed:
                return {
                    "type": "action",
                    "action": self._normalize_action_name(str(parsed.get("action", ""))),
                    "args": parsed.get("args", {}) if isinstance(parsed.get("args"), dict) else {},
                    "message": str(parsed.get("message", "")),
                }
            if "message" in parsed:
                return {"type": "reply", "message": str(parsed.get("message", ""))}

        message = (content or "").strip()
        if not message:
            message = "Empty response from model."
        return {"type": "reply", "message": message}

    def _normalize_action_name(self, action: str) -> str:
        if not action:
            return action
        lowered = action.strip().lower()
        alias_map = {
            "open_url": "system.open_url",
            "openurl": "system.open_url",
            "open-web": "system.open_url",
            "open_web": "system.open_url",
            "browser.open": "system.open_url",
            "open_path": "system.open_path",
            "openpath": "system.open_path",
            "open_file": "file.open",
            "openfile": "file.open",
            "launch": "system.launch",
            "launch_app": "system.launch",
            "start_app": "system.launch",
        }
        return alias_map.get(lowered, action)

    def _language_instruction(self) -> str:
        language = (self._config.language or "english").strip().lower()
        if language == "russian":
            return "Reply to the user in Russian unless they ask for another language."
        if language == "uzbek":
            return "Reply to the user in Uzbek (Latin script) unless they ask for another language."
        return "Reply to the user in English unless they ask for another language."

    def _rule_based_action(self, text: str) -> dict | None:
        if not text:
            return None
        raw = text.strip()
        if not raw:
            return None
        lowered = raw.lower()

        url_match = self._url_re.search(raw)
        if url_match:
            url = url_match.group(1).rstrip(").,!?\\\"'")
            if url.startswith("www."):
                url = "https://" + url
            return {
                "type": "action",
                "action": "system.open_url",
                "args": {"url": url},
                "message": "Opening the link.",
            }

        tokens = re.findall(r"[\w']+", lowered)

        open_verbs = {
            "open",
            "launch",
            "start",
            "run",
            "go",
            "visit",
            "och",
            "oching",
            "ochib",
            "kir",
            "kiring",
            "kirib",
            "ishla",
            "ishga",
            "tushir",
            "\u043e\u0442\u043a\u0440\u043e\u0439",
            "\u043e\u0442\u043a\u0440\u043e\u0439\u0442\u0435",
            "\u043e\u0442\u043a\u0440\u044b\u0442\u044c",
            "\u0437\u0430\u043f\u0443\u0441\u0442\u0438",
            "\u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c",
        }
        play_verbs = {
            "play",
            "watch",
            "listen",
            "yoq",
            "yoqib",
            "qoy",
            "quy",
            "qo'y",
            "eshit",
            "\u0432\u043a\u043b\u044e\u0447\u0438",
            "\u043f\u043e\u0441\u0442\u0430\u0432\u044c",
        }
        search_verbs = {
            "search",
            "find",
            "lookup",
            "qidir",
            "izla",
            "\u043d\u0430\u0439\u0434\u0438",
            "\u043f\u043e\u0438\u0449\u0438",
        }

        has_open = any(token in open_verbs for token in tokens)
        has_play = any(token in play_verbs for token in tokens)
        has_search = any(token in search_verbs for token in tokens)
        if not (has_open or has_play or has_search):
            return None

        youtube_keys = {
            "yt",
            "ytb",
            "youtube",
            "utub",
            "yutub",
            "\u044e\u0442\u0443\u0431",
            "\u044e\u0442\u0431",
            "\u044e\u0442\u044c\u044e\u0431",
        }
        if any(key in youtube_keys for key in tokens) or "youtube" in lowered:
            drop_words = set(open_verbs) | set(play_verbs) | set(search_verbs) | set(youtube_keys)
            query = self._extract_query(lowered, drop_words)
            if query and has_play:
                return {
                    "type": "action",
                    "action": "system.open_url",
                    "args": {"provider": "youtube", "query": query, "play": True},
                    "message": f"Playing the first YouTube result for: {query}",
                }
            if query and has_search and not has_play:
                return {
                    "type": "action",
                    "action": "system.open_url",
                    "args": {"provider": "youtube", "query": query, "play": False},
                    "message": f"Opening YouTube search for: {query}",
                }
            return {
                "type": "action",
                "action": "system.open_url",
                "args": {"url": "https://www.youtube.com"},
                "message": "Opening YouTube.",
            }

        if any(key in tokens for key in ("telegram", "\u0442\u0435\u043b\u0435\u0433\u0440\u0430\u043c")):
            return {
                "type": "action",
                "action": "system.launch",
                "args": {"target": "telegram"},
                "message": "Opening Telegram.",
            }

        if any(key in tokens for key in ("explorer", "\u043f\u0440\u043e\u0432\u043e\u0434\u043d\u0438\u043a")):
            return {
                "type": "action",
                "action": "system.launch",
                "args": {"target": "explorer"},
                "message": "Opening Explorer.",
            }

        return None

    def _extract_query(self, lowered: str, drop_words: set) -> str:
        tokens = re.findall(r"[\w']+", lowered)
        stopwords = {
            "the",
            "a",
            "an",
            "please",
            "pls",
            "and",
            "then",
            "to",
            "for",
            "in",
            "on",
            "ga",
            "da",
            "ni",
            "mi",
            "va",
            "yoq",
            "qoy",
            "quy",
            "qo",
            "qo'y",
            "y",
            "i",
            "mu",
            "\u0438",
            "\u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430",
            "\u043d\u0430",
            "\u0432",
        }
        blacklist = set(drop_words) | stopwords
        query_tokens = [token for token in tokens if token not in blacklist]
        return " ".join(query_tokens).strip()
