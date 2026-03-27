import hashlib


class AnalysisCache:
    def __init__(self):
        self._cache: dict[str, dict] = {}

    def get(self, sentence: str, variant: str) -> dict | None:
        return self._cache.get(self._key(sentence, variant))

    def put(self, sentence: str, variant: str, result: dict) -> None:
        self._cache[self._key(sentence, variant)] = result

    def clear(self) -> None:
        self._cache.clear()

    def _key(self, sentence: str, variant: str) -> str:
        return hashlib.sha256(f"{variant}:{sentence}".encode()).hexdigest()


cache = AnalysisCache()


def cache_key(sentence: str, variant: str) -> str:
    return cache._key(sentence, variant)


def get(sentence: str, variant: str) -> dict | None:
    return cache.get(sentence, variant)


def put(sentence: str, variant: str, result: dict) -> None:
    cache.put(sentence, variant, result)


def clear() -> None:
    cache.clear()
