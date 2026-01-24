import os
import subprocess


def launch_app(target: str, args: list) -> dict:
    if os.path.exists(target):
        subprocess.Popen([target] + list(args))
    else:
        subprocess.Popen([target] + list(args), shell=True)
    return {"launched": target}


def open_path(path: str) -> dict:
    os.startfile(path)
    return {"opened": path}
