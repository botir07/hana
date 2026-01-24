import json
import os
import sqlite3
from datetime import datetime

from core.config import Config
from core.safety import assess_action, normalize_path
from tools import file_tools, system_tools


class Executor:
    def __init__(self) -> None:
        self._config = Config()
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self._config.db_path), exist_ok=True)
        with sqlite3.connect(self._config.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS actions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "timestamp TEXT, action TEXT, args TEXT, status TEXT, message TEXT)"
            )

    def _log(self, action: str, args: dict, status: str, message: str) -> None:
        with sqlite3.connect(self._config.db_path) as conn:
            conn.execute(
                "INSERT INTO actions (timestamp, action, args, status, message) VALUES (?, ?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), action, json.dumps(args), status, message),
            )

    def execute_action(self, action: str, args: dict, confirmed: bool) -> dict:
        allowed, risky, reason = assess_action(action, args)
        if not allowed:
            self._log(action, args, "denied", reason)
            return {"status": "denied", "message": reason}

        if risky and not confirmed:
            return {"status": "needs_confirmation", "message": reason}

        try:
            result = self._dispatch(action, args)
            self._log(action, args, "success", "OK")
            return {"status": "success", "message": "Action executed.", "result": result}
        except Exception as exc:
            self._log(action, args, "error", str(exc))
            return {"status": "error", "message": str(exc)}

    def _dispatch(self, action: str, args: dict) -> dict:
        if action == "file.open":
            return file_tools.open_file(normalize_path(args["path"]))
        if action == "file.rename":
            return file_tools.rename_file(normalize_path(args["src"]), normalize_path(args["dst"]))
        if action == "file.move":
            return file_tools.move_file(normalize_path(args["src"]), normalize_path(args["dst"]))
        if action == "file.delete":
            return file_tools.delete_file(normalize_path(args["path"]), self._config.trash_dir)
        if action == "file.create_folder":
            return file_tools.create_folder(normalize_path(args["path"]))
        if action == "system.launch":
            return system_tools.launch_app(args["target"], args.get("args", []))
        if action == "system.open_path":
            return system_tools.open_path(normalize_path(args["path"]))
        raise ValueError(f"Unknown action: {action}")
