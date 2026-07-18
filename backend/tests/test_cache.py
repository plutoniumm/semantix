from backend.cache import AnalysisCache

RESULT = {
    "issues": [
        {
            "type": "style",
            "original_fragment": "very",
            "suggestion": "highly",
            "explanation": "x",
        }
    ],
    "parse_error": False,
}


def test_miss_returns_none(tmp_path):
    c = AnalysisCache(tmp_path / "t.db")
    assert c.get("some sentence", "british") is None


def test_put_get_roundtrip(tmp_path):
    c = AnalysisCache(tmp_path / "t.db")
    c.put("some sentence", "british", RESULT)
    assert c.get("some sentence", "british") == RESULT


def test_variant_separates_keys(tmp_path):
    c = AnalysisCache(tmp_path / "t.db")
    c.put("some sentence", "british", RESULT)
    assert c.get("some sentence", "american") is None


def test_persists_across_instances(tmp_path):
    path = tmp_path / "t.db"
    AnalysisCache(path).put("some sentence", "british", RESULT)
    assert AnalysisCache(path).get("some sentence", "british") == RESULT


def test_clear(tmp_path):
    c = AnalysisCache(tmp_path / "t.db")
    c.put("some sentence", "british", RESULT)
    c.clear()
    assert c.get("some sentence", "british") is None


def test_model_separates_keys(tmp_path):
    c = AnalysisCache(tmp_path / "t.db")
    c.put("some sentence", "british", RESULT, model="model-a")
    assert c.get("some sentence", "british", model="model-b") is None
    assert c.get("some sentence", "british", model="model-a") == RESULT


def test_put_overwrites(tmp_path):
    c = AnalysisCache(tmp_path / "t.db")
    c.put("some sentence", "british", RESULT)
    c.put("some sentence", "british", {"issues": [], "parse_error": False})
    assert c.get("some sentence", "british") == {"issues": [], "parse_error": False}
