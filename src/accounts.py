"""Local, file-backed user accounts for self-service registration. No external deps."""

import hashlib
import hmac
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
PBKDF2_ITERATIONS = 310_000


class UserStore:
    """JSON-backed username/password store with salted PBKDF2 hashes."""

    def __init__(self, path: Path, *, max_users: int = 200, reserved_usernames: frozenset[str] = frozenset()):
        self._path = path
        self._max_users = max_users
        self._reserved = {name.lower() for name in reserved_usernames if name}
        self._lock = threading.Lock()

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text("utf-8"))
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _save(self, users: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(f"{self._path.suffix}.tmp-{os.getpid()}")
        tmp_path.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._path)

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()

    def register(self, username: str, password: str) -> None:
        username = username.strip().lower()
        if not USERNAME_PATTERN.match(username):
            raise ValueError("用户名需为 3-32 位英文字母、数字或下划线")
        if not (MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH):
            raise ValueError(f"密码长度需为 {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} 位")
        if username in self._reserved:
            raise ValueError("该用户名已被保留，请更换其他用户名")
        with self._lock:
            users = self._load()
            if username in users:
                raise ValueError("用户名已被注册，请更换其他用户名")
            if len(users) >= self._max_users:
                raise ValueError("注册名额已满，请联系管理员")
            salt = os.urandom(16)
            users[username] = {
                "salt": salt.hex(),
                "hash": self._hash_password(password, salt),
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            self._save(users)

    def verify(self, username: str, password: str) -> bool:
        username = username.strip().lower()
        with self._lock:
            users = self._load()
        record = users.get(username)
        if record is None:
            return False
        salt = bytes.fromhex(record["salt"])
        expected = record["hash"]
        actual = self._hash_password(password, salt)
        return hmac.compare_digest(actual, expected)

    def has_any_user(self) -> bool:
        with self._lock:
            return bool(self._load())
