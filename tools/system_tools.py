import os
import subprocess
import urllib.parse
import webbrowser


def launch_app(target: str, args: list) -> dict:
    if os.path.exists(target):
        subprocess.Popen([target] + list(args))
    else:
        subprocess.Popen([target] + list(args), shell=True)
    return {"launched": target}


def open_path(path: str) -> dict:
    os.startfile(path)
    return {"opened": path}


def open_url(args: dict) -> dict:
    url = args.get("url")
    query = args.get("query")
    if not url and query:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
    if not url:
        raise ValueError("Missing url or query.")
    webbrowser.open(url)
    return {"opened": url}
