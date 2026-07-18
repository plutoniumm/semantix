from fastapi.testclient import TestClient

import backend.main as main

# No context manager: lifespan (vite spawn, session sweeper) must not run in tests.
client = TestClient(main.app)


def test_analyze_creates_session():
    resp = client.post(
        "/analyze", json={"text": "Hello there world.", "variant": "british"}
    )
    assert resp.status_code == 200
    assert "session_id" in resp.json()


def test_analyze_rejects_bad_variant():
    resp = client.post("/analyze", json={"text": "x", "variant": "australian"})
    assert resp.status_code == 422


def test_stream_unknown_session_404():
    resp = client.get("/analyze/stream/not-a-real-session")
    assert resp.status_code == 404


def test_stream_session_is_single_use(monkeypatch):
    async def no_results(text, variant, mode="plain"):
        return
        yield  # makes this an async generator

    monkeypatch.setattr(main, "analyze_text", no_results)
    session_id = client.post(
        "/analyze", json={"text": "Hello there world.", "variant": "british"}
    ).json()["session_id"]
    assert client.get(f"/analyze/stream/{session_id}").status_code == 200
    assert client.get(f"/analyze/stream/{session_id}").status_code == 404


def test_health_reports_ollama_state(monkeypatch):
    async def fake_probe():
        return False

    monkeypatch.setattr(main, "probe_llm", fake_probe)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama"] is False
    assert isinstance(body["model"], str)


def test_cache_clear():
    resp = client.post("/cache/clear")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_models_endpoint(monkeypatch):
    async def fake_list():
        return ["model-a", "model-b"]

    async def fake_style():
        return "openai"

    monkeypatch.setattr(main.llm, "list_models", fake_list)
    monkeypatch.setattr(main.llm, "detect_style", fake_style)
    resp = client.get("/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["models"] == ["model-a", "model-b"]
    assert body["api_style"] == "openai"
    assert isinstance(body["analyzer_model"], str)
    assert isinstance(body["translate_model"], str)


def test_models_endpoint_survives_llm_down(monkeypatch):
    async def boom():
        raise RuntimeError("down")

    monkeypatch.setattr(main.llm, "list_models", boom)
    resp = client.get("/models")
    assert resp.status_code == 200
    assert resp.json()["models"] == []
    assert resp.json()["api_style"] is None


def test_select_model(monkeypatch, tmp_path):
    from backend import config

    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "cfg.json")
    config.load()
    try:
        resp = client.post(
            "/models/select", json={"target": "analyzer", "model": "picked-model"}
        )
        assert resp.status_code == 200
        assert resp.json()["analyzer_model"] == "picked-model"
        assert config.get()["analyzer_model"] == "picked-model"
    finally:
        monkeypatch.undo()
        config.load()


def test_select_model_rejects_bad_target():
    resp = client.post("/models/select", json={"target": "nonsense", "model": "x"})
    assert resp.status_code == 422


def test_analyze_sentence_endpoint(monkeypatch):
    async def fake_analyze(sentence, variant, idx):
        return {
            "sentence_index": idx,
            "original": sentence,
            "issues": [],
            "parse_error": False,
        }

    monkeypatch.setattr(main, "analyze_sentence", fake_analyze)
    resp = client.post(
        "/analyze/sentence",
        json={
            "sentence": "A test sentence here.",
            "variant": "british",
            "sentence_index": 3,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["sentence_index"] == 3
    assert resp.json()["original"] == "A test sentence here."
