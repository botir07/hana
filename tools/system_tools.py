import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import webbrowser


def _youtube_search_url(query: str) -> str:
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.youtube.com/results?search_query={encoded}"


def _youtube_first_url(query: str) -> str | None:
    search_url = _youtube_search_url(query)
    try:
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except Exception:
        return None

    match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
    if not match:
        match = re.search(r"watch\\?v=([a-zA-Z0-9_-]{11})", html)
    if not match:
        return None
    return f"https://www.youtube.com/watch?v={match.group(1)}&autoplay=1"


def _is_url_like(target: str) -> bool:
    lowered = target.lower()
    return "://" in lowered or lowered.startswith("www.")


def _candidate_path(base: str | None, *parts: str) -> str | None:
    if not base:
        return None
    return os.path.join(base, *parts)


def _resolve_windows_target(target: str) -> str | None:
    trimmed = target.strip().strip('"')
    if os.path.exists(trimmed):
        return trimmed

    if os.path.dirname(trimmed):
        if not trimmed.lower().endswith(".exe"):
            candidate = trimmed + ".exe"
            if os.path.exists(candidate):
                return candidate
        return None

    lowered = trimmed.lower()
    if lowered in {"telegram", "telegram.exe", "tg"}:
        env_local = os.environ.get("LOCALAPPDATA")
        env_appdata = os.environ.get("APPDATA")
        env_pf = os.environ.get("ProgramFiles")
        env_pf86 = os.environ.get("ProgramFiles(x86)")
        candidates = [
            _candidate_path(env_appdata, "Telegram Desktop", "Telegram.exe"),
            _candidate_path(env_local, "Telegram Desktop", "Telegram.exe"),
            _candidate_path(env_local, "Programs", "Telegram Desktop", "Telegram.exe"),
            _candidate_path(env_pf, "Telegram Desktop", "Telegram.exe"),
            _candidate_path(env_pf86, "Telegram Desktop", "Telegram.exe"),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

    if lowered in {"explorer", "explorer.exe"}:
        windir = os.environ.get("WINDIR", "C:\\Windows")
        candidate = os.path.join(windir, "explorer.exe")
        if os.path.exists(candidate):
            return candidate

    found = shutil.which(trimmed)
    if found:
        return found
    if not lowered.endswith(".exe"):
        found = shutil.which(trimmed + ".exe")
        if found:
            return found
    return None


def launch_app(target: str, args: list) -> dict:
    if not target:
        raise ValueError("Missing target argument.")
    args = list(args or [])

    if os.name == "nt":
        resolved = _resolve_windows_target(target)
        if resolved:
            subprocess.Popen([resolved] + args)
            return {"launched": resolved}
        if _is_url_like(target):
            webbrowser.open(target)
            return {"launched": target}
        if target.lower() in {"telegram", "telegram.exe", "tg"}:
            if webbrowser.open("tg://"):
                return {"launched": "tg://"}
        try:
            subprocess.Popen(["cmd", "/c", "start", "", target] + args, shell=False)
            return {"launched": target}
        except Exception as exc:
            raise ValueError(f"Unable to launch app: {target}") from exc

    resolved = shutil.which(target)
    if resolved:
        subprocess.Popen([resolved] + args)
        return {"launched": resolved}
    if _is_url_like(target):
        webbrowser.open(target)
        return {"launched": target}
    raise ValueError(f"Unable to launch app: {target}")


def open_path(path: str) -> dict:
    os.startfile(path)
    return {"opened": path}


def open_url(args: dict) -> dict:
    url = args.get("url")
    query = args.get("query")
    provider = (args.get("provider") or "").lower()
    play = bool(args.get("play") or args.get("play_first"))

    if provider == "youtube":
        if query:
            if play:
                url = _youtube_first_url(query) or _youtube_search_url(query)
            else:
                url = _youtube_search_url(query)
        elif not url:
            url = "https://www.youtube.com"

    if not url and query:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
    if not url:
        raise ValueError("Missing url or query.")
    webbrowser.open(url)
    return {"opened": url}
