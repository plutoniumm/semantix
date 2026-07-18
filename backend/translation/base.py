from abc import ABC, abstractmethod


class BaseTranslator(ABC):

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Translate plain text. source/target are NLLB BCP-47 codes (e.g. eng_Latn)."""
        ...

    async def translate_image(
        self,
        image_bytes: bytes,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Translate text extracted from an image. Override in multimodal implementations."""
        raise NotImplementedError("This translator does not support image input.")
