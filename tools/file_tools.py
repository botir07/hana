import os
import shutil
import time


def open_file(path: str) -> dict:
    os.startfile(path)
    return {"opened": path}


def rename_file(src: str, dst: str) -> dict:
    os.rename(src, dst)
    return {"renamed": src, "to": dst}


def move_file(src: str, dst: str) -> dict:
    shutil.move(src, dst)
    return {"moved": src, "to": dst}


def delete_file(path: str, trash_dir: str) -> dict:
    os.makedirs(trash_dir, exist_ok=True)
    base = os.path.basename(path)
    timestamp = time.strftime("%Y%m%d%H%M%S")
    target = os.path.join(trash_dir, f"{base}.{timestamp}")
    shutil.move(path, target)
    return {"deleted": path, "trashed": target}


def create_folder(path: str) -> dict:
    os.makedirs(path, exist_ok=True)
    return {"created": path}
