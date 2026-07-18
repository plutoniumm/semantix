from backend import llm
from backend.config import get as get_config
from backend.translation.base import BaseTranslator

READ_TIMEOUT = 60.0


class OllamaTranslator(BaseTranslator):
    """Translates via the configured LLM endpoint (OpenAI v1 or Ollama native;
    see backend.llm). The model comes from config so picker changes apply
    without a restart."""

    async def translate_text(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        system = (
            "You are a professional translator. "
            f"Translate the user's text from {source_lang} into {target_lang}. "
            "Return only the translated text, no explanation, no quotes."
        )
        result = await llm.chat(
            model=get_config()["translate_model"],
            system=system,
            user=text,
            read_timeout=READ_TIMEOUT,
        )
        return result.strip()
