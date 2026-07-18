import json
import os
import threading
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "semantix.config.json"

DEFAULTS = {
    "base_url": "http://100.117.92.56:11434",
    "api_style": "auto",
    "api_key": "",
    "analyzer_model": "gemma-e4b:latest",
    "translate_model": "gemma4:26b",
}

_lock = threading.Lock()
_config: dict | None = None


def _env_overrides(cfg: dict) -> dict:
    if os.getenv("OLLAMA_BASE"):
        cfg["base_url"] = os.getenv("OLLAMA_BASE")
    if os.getenv("OPENAI_BASE_URL"):
        cfg["base_url"] = os.getenv("OPENAI_BASE_URL")
        cfg["api_style"] = "openai"
    if os.getenv("OPENAI_API_KEY"):
        cfg["api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("OLLAMA_MODEL"):
        cfg["analyzer_model"] = os.getenv("OLLAMA_MODEL")
    if os.getenv("TRANSLATE_MODEL"):
        cfg["translate_model"] = os.getenv("TRANSLATE_MODEL")
    return cfg


def _read_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def load(path: Path | None = None) -> dict:
    """(Re)load config from disk, creating the file with defaults if absent.

    Precedence: environment variables > config file > built-in defaults.
    """
    global _config
    path = path or CONFIG_PATH
    with _lock:
        cfg = dict(DEFAULTS)
        if path.exists():
            cfg.update(_read_file(path))
        else:
            try:
                path.write_text(json.dumps(cfg, indent=2) + "\n")
            except OSError:
                pass
        _config = _env_overrides(cfg)
    return _config


def get() -> dict:
    return _config if _config is not None else load()


def set_model(target: str, model: str, path: Path | None = None) -> dict:
    """Set the analyzer or translator model, persisting to the config file."""
    path = path or CONFIG_PATH
    key = "analyzer_model" if target == "analyzer" else "translate_model"
    cfg = get()
    with _lock:
        cfg[key] = model
        on_disk = dict(DEFAULTS)
        if path.exists():
            on_disk.update(_read_file(path))
        on_disk[key] = model
        try:
            path.write_text(json.dumps(on_disk, indent=2) + "\n")
        except OSError:
            pass
    return cfg
