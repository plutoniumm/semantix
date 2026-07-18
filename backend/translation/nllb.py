import asyncio
from functools import lru_cache
from backend.translation.base import BaseTranslator

MODEL_ID = "Emilio407/nllb-200-3.3B-4bit"


@lru_cache(maxsize=1)
def _load_model():
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID, device_map="auto")
    return tokenizer, model


class NLLBTranslator(BaseTranslator):

    async def translate_text(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run, text, source_lang, target_lang
        )

    def _run(self, text: str, source_lang: str, target_lang: str) -> str:
        tokenizer, model = _load_model()
        tokenizer.src_lang = source_lang
        inputs = tokenizer(
            text, return_tensors="pt", padding=True, truncation=True, max_length=512
        )
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        target_lang_id = tokenizer.convert_tokens_to_ids(target_lang)
        output_ids = model.generate(
            **inputs,
            forced_bos_token_id=target_lang_id,
            max_new_tokens=512,
        )
        return tokenizer.decode(output_ids[0], skip_special_tokens=True)
