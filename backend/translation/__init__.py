import os
from backend.translation.base import BaseTranslator


def get_translator() -> BaseTranslator:
    backend = os.getenv("TRANSLATE_BACKEND", "ollama").lower()
    if backend == "ollama":
        from backend.translation.ollama import OllamaTranslator

        return OllamaTranslator()
    from backend.translation.nllb import NLLBTranslator

    return NLLBTranslator()


_translator: BaseTranslator | None = None


def translator() -> BaseTranslator:
    global _translator
    if _translator is None:
        _translator = get_translator()
    return _translator
