import asyncio
import json

import pytest

from backend import config, llm


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    for var in (
        "OLLAMA_BASE",
        "OLLAMA_MODEL",
        "TRANSLATE_MODEL",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    path = tmp_path / "cfg.json"
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    yield path
    monkeypatch.undo()
    config.load()  # restore real config for other tests


def test_load_creates_file_with_defaults(isolated_config):
    cfg = config.load()
    assert isolated_config.exists()
    assert cfg == config.DEFAULTS
    assert cfg["api_style"] == "auto"


def test_load_merges_file_over_defaults(isolated_config):
    isolated_config.write_text(json.dumps({"analyzer_model": "custom:7b"}))
    cfg = config.load()
    assert cfg["analyzer_model"] == "custom:7b"
    assert cfg["base_url"] == config.DEFAULTS["base_url"]


def test_env_overrides_win(isolated_config, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "env-model")
    cfg = config.load()
    assert cfg["base_url"] == "https://api.example.com/v1"
    assert cfg["api_style"] == "openai"
    assert cfg["analyzer_model"] == "env-model"


def test_set_model_persists(isolated_config):
    config.load()
    cfg = config.set_model("analyzer", "new-model:latest")
    assert cfg["analyzer_model"] == "new-model:latest"
    on_disk = json.loads(isolated_config.read_text())
    assert on_disk["analyzer_model"] == "new-model:latest"
    assert config.get()["analyzer_model"] == "new-model:latest"


def test_set_model_translator(isolated_config):
    config.load()
    config.set_model("translator", "trans-model")
    assert json.loads(isolated_config.read_text())["translate_model"] == "trans-model"


def test_llm_root_strips_v1_suffix(isolated_config):
    isolated_config.write_text(json.dumps({"base_url": "http://host:1234/v1"}))
    config.load()
    assert llm._root() == "http://host:1234"
    isolated_config.write_text(json.dumps({"base_url": "http://host:1234"}))
    config.load()
    assert llm._root() == "http://host:1234"


def test_detect_style_respects_forced_style(isolated_config):
    isolated_config.write_text(json.dumps({"api_style": "ollama"}))
    config.load()
    assert asyncio.run(llm.detect_style()) == "ollama"
    isolated_config.write_text(json.dumps({"api_style": "openai"}))
    config.load()
    assert asyncio.run(llm.detect_style()) == "openai"


def test_llm_headers_include_api_key(isolated_config):
    isolated_config.write_text(json.dumps({"api_key": "sk-test"}))
    config.load()
    assert llm._headers()["Authorization"] == "Bearer sk-test"
    isolated_config.write_text(json.dumps({"api_key": ""}))
    config.load()
    assert "Authorization" not in llm._headers()
