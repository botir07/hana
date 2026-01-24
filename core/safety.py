import os


PROTECTED_DIRS = [
    r"C:\\Windows",
    r"C:\\Program Files",
    r"C:\\Program Files (x86)",
]


KNOWN_DIRS = {
    "downloads": "Downloads",
    "documents": "Documents",
    "desktop": "Desktop",
}


def normalize_path(path: str) -> str:
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded):
        key = expanded.strip().lower()
        if key in KNOWN_DIRS:
            return os.path.join(os.path.expanduser("~"), KNOWN_DIRS[key])
    return os.path.abspath(expanded)


def is_within_protected(path: str) -> bool:
    normalized = normalize_path(path)
    for protected in PROTECTED_DIRS:
        try:
            common = os.path.commonpath([normalized, protected])
        except ValueError:
            continue
        if common == protected:
            return True
    return False


def validate_path_exists(path: str) -> bool:
    return os.path.exists(normalize_path(path))


def assess_action(action: str, args: dict) -> tuple[bool, bool, str]:
    risky = action in {"file.delete", "file.rename", "file.move"}

    if action in {"file.open", "file.delete", "system.open_path", "file.create_folder"}:
        path = args.get("path")
        if not path:
            return False, False, "Missing path argument."
        if is_within_protected(path):
            return False, False, "Target is in a protected directory."
        if not validate_path_exists(path):
            if action == "file.create_folder":
                return True, False, "OK"
            return False, False, "Target path does not exist."
        return True, risky, "Confirmation required for risky action." if risky else "OK"

    if action in {"file.rename", "file.move"}:
        src = args.get("src")
        dst = args.get("dst")
        if not src or not dst:
            return False, False, "Missing src or dst argument."
        if is_within_protected(src) or is_within_protected(dst):
            return False, False, "Source or destination is in a protected directory."
        if not validate_path_exists(src):
            return False, False, "Source path does not exist."
        return True, risky, "Confirmation required for risky action."

    if action == "system.launch":
        target = args.get("target")
        if not target:
            return False, False, "Missing target argument."
        if os.path.exists(target) and is_within_protected(target):
            return False, False, "Target is in a protected directory."
        return True, False, "OK"

    if action == "system.open_url":
        url = args.get("url") or args.get("query")
        if not url:
            return False, False, "Missing url or query argument."
        return True, False, "OK"

    return False, False, f"Unknown action: {action}"
