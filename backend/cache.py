import hashlib
import json
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent / "cache.db"


class AnalysisCache:
    def __init__(self, path: str | Path = DB_PATH):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._conn.commit()

    def get(self, sentence: str, variant: str, model: str = "") -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM cache WHERE key = ?",
                (self._key(sentence, variant, model),),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, sentence: str, variant: str, result: dict, model: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (self._key(sentence, variant, model), json.dumps(result)),
            )
            self._conn.commit()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache")
            self._conn.commit()

    def _key(self, sentence: str, variant: str, model: str = "") -> str:
        return hashlib.sha256(f"{variant}:{model}:{sentence}".encode()).hexdigest()


cache = AnalysisCache()


def cache_key(sentence: str, variant: str, model: str = "") -> str:
    return cache._key(sentence, variant, model)


def get(sentence: str, variant: str, model: str = "") -> dict | None:
    return cache.get(sentence, variant, model)


def put(sentence: str, variant: str, result: dict, model: str = "") -> None:
    cache.put(sentence, variant, result, model)


def clear() -> None:
    cache.clear()
