import json
import asyncio
import re
import nltk
import httpx
from backend.cache import cache

nltk.download("punkt_tab", quiet=True)


OLLAMA_BASE = "http://100.117.92.56:11434"
OLLAMA_URL = f"{OLLAMA_BASE}/api/generate"
OLLAMA_MODEL = "lfm2:latest"
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 30.0
MIN_WORDS = 3

SYSTEM_PROMPT_TEMPLATE = (
    "You are a professional writing assistant. "
    "Analyse the following sentence for grammar, spelling, style, and punctuation errors. "
    "Use {variant} English conventions. "
    "Return a JSON object only, no prose. Schema: "
    '{{"issues": [{{"type": "grammar|spelling|style|punctuation", '
    '"original_fragment": "...", "suggestion": "...", "explanation": "..."}}]}} '
    'If there are no issues, return {{"issues": []}}.'
)


class LaTeXPreprocessor:
    MATH_ENVS = (
        "align", "align*", "equation", "equation*", "gather", "gather*",
        "multline", "multline*", "eqnarray", "eqnarray*", "displaymath",
    )
    NON_PROSE_ENVS = (
        "algorithm", "algorithmic", "lstlisting", "verbatim",
        "tabular", "array", "pmatrix", "bmatrix", "vmatrix", "matrix",
    )
    FORMATTING_CMDS = (
        "textit", "textbf", "emph", "texttt", "textrm", "textsc", "text", "mbox",
    )
    SECTION_CMDS = (
        "section", "subsection", "subsubsection", "paragraph", "title",
    )
    CITE_CMDS = ("cite", "citep", "citet", "citealt", "nocite")
    REF_CMDS  = ("ref", "eqref", "pageref")
    METADATA_CMDS = (
        "label", "bibliography", "bibliographystyle", "newcommand", "renewcommand",
        "acmJournal", "acmVolume", "acmNumber", "acmArticle", "acmYear", "acmDOI",
        "setcopyright", "author", "affiliation", "institution", "department",
        "city", "country", "date", "keywords", "hspace", "vspace",
        "setcounter", "addtocounter", "usepackage", "documentclass",
    )

    def preprocess(self, text: str) -> str:
        text = self._extract_body(text)
        text = self._strip_math_envs(text)
        text = self._strip_display_math(text)
        text = self._strip_inline_math(text)
        text = self._strip_non_prose_envs(text)
        text = self._strip_comments(text)
        text = self._handle_figures(text)
        text = self._expand_formatting(text)
        text = self._expand_sections(text)
        text = self._handle_cite_refs(text)
        text = self._strip_remaining(text)
        text = self._normalize_whitespace(text)
        return text

    @staticmethod
    def has_residual_latex(text: str) -> bool:
        return bool(re.search(r"\\[a-zA-Z]", text))

    def _extract_body(self, text: str) -> str:
        m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.DOTALL)
        return m.group(1) if m else text

    def _strip_math_envs(self, text: str) -> str:
        for env in self.MATH_ENVS:
            esc = re.escape(env)
            text = re.sub(
                r"\\begin\{" + esc + r"\}.*?\\end\{" + esc + r"\}",
                " ", text, flags=re.DOTALL,
            )
        return text

    def _strip_display_math(self, text: str) -> str:
        text = re.sub(r"\\\[.*?\\\]", " ", text, flags=re.DOTALL)
        text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.DOTALL)
        return text

    def _strip_inline_math(self, text: str) -> str:
        return re.sub(r"\$[^$\n]*\$", " ", text)

    def _strip_non_prose_envs(self, text: str) -> str:
        for env in self.NON_PROSE_ENVS:
            esc = re.escape(env)
            text = re.sub(
                r"\\begin\{" + esc + r"\*?\}.*?\\end\{" + esc + r"\*?\}",
                " ", text, flags=re.DOTALL,
            )
        return text

    def _strip_comments(self, text: str) -> str:
        return re.sub(r"(?<!\\)%[^\n]*", "", text)

    def _handle_figures(self, text: str) -> str:
        text = re.sub(r"\\caption\{([^}]*)\}", r"\1", text)
        text = re.sub(r"\\(begin|end)\{(figure|table)\*?\}(\[[^\]]*\])?", "", text)
        text = re.sub(r"\\includegraphics(\[[^\]]*\])?\{[^}]*\}", "", text)
        return text

    def _expand_formatting(self, text: str) -> str:
        for cmd in self.FORMATTING_CMDS:
            text = re.sub(r"\\" + cmd + r"\{([^}]*)\}", r"\1", text)
        return text

    def _expand_sections(self, text: str) -> str:
        for cmd in self.SECTION_CMDS:
            text = re.sub(r"\\" + cmd + r"\*?\{([^}]*)\}", r"\1. ", text)
        return text

    def _handle_cite_refs(self, text: str) -> str:
        for cmd in self.CITE_CMDS:
            text = re.sub(r"\s*~\\" + cmd + r"(\[[^\]]*\])?\{[^}]*\}", "", text)
        for cmd in self.REF_CMDS:
            text = re.sub(r"\s*~\\" + cmd + r"(\[[^\]]*\])?\{[^}]*\}", " X", text)
        for cmd in self.REF_CMDS:
            text = re.sub(r"\\" + cmd + r"(\[[^\]]*\])?\{[^}]*\}", "X", text)
        for cmd in self.CITE_CMDS + self.METADATA_CMDS:
            text = re.sub(r"\\" + cmd + r"(\[[^\]]*\])?\{[^}]*\}", "", text)
        return text

    def _strip_remaining(self, text: str) -> str:
        text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?\{[^}]*\}", " ", text)
        text = re.sub(r"\\(begin|end)\{[^}]*\}", "", text)
        text = re.sub(r"\\[a-zA-Z@]+\*?", " ", text)
        text = re.sub(r"[{}]", "", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        text = text.replace("~", " ")
        text = text.replace("---", "\u2014").replace("--", "\u2013")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class TextAnalyzer:
    BATCH_SIZE = 3

    def __init__(self):
        self._preprocessor = LaTeXPreprocessor()

    async def probe_ollama(self) -> bool:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=CONNECT_TIMEOUT, read=5.0, write=5.0, pool=5.0)
            ) as client:
                await client.get(OLLAMA_BASE)
            return True
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def split(self, text: str, mode: str = "plain") -> list[str]:
        if not text or not text.strip():
            return []
        working = self._preprocessor.preprocess(text) if mode == "latex" else text
        sentences = nltk.sent_tokenize(working)
        result = []
        for s in sentences:
            if not s.strip() or len(s.split()) < MIN_WORDS:
                continue
            if mode == "latex" and LaTeXPreprocessor.has_residual_latex(s):
                continue
            result.append(s)
        return result

    async def analyze_sentence(self, sentence: str, variant: str, idx: int) -> dict:
        cached = cache.get(sentence, variant)
        if cached is not None:
            return {**cached, "sentence_index": idx, "original": sentence}

        variant_label = "British" if variant == "british" else "American"
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(variant=variant_label)

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT, write=5.0, pool=5.0)
            ) as client:
                response = await client.post(
                    OLLAMA_URL,
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": sentence,
                        "system": system_prompt,
                        "format": "json",
                        "stream": False,
                    },
                )
            raw = response.json().get("response", "")
            data = json.loads(raw)
            issues = data.get("issues", [])
            result = {"issues": issues, "parse_error": False}
            cache.put(sentence, variant, result)
            return {**result, "sentence_index": idx, "original": sentence}

        except (httpx.TimeoutException, httpx.ConnectError, json.JSONDecodeError, KeyError, ValueError):
            return {
                "sentence_index": idx,
                "original": sentence,
                "issues": [],
                "parse_error": True,
            }

    async def analyze_text(self, text: str, variant: str, mode: str = "plain"):
        sentences = self.split(text, mode)

        if not sentences:
            return

        if not await self.probe_ollama():
            raise RuntimeError("LLM unavailable")

        for i in range(0, len(sentences), self.BATCH_SIZE):
            batch = sentences[i : i + self.BATCH_SIZE]
            results = await asyncio.gather(*[
                self.analyze_sentence(s, variant, i + j)
                for j, s in enumerate(batch)
            ])
            for r in results:
                yield r


_analyzer = TextAnalyzer()


def split_sentences(text: str, mode: str = "plain") -> list[str]:
    return _analyzer.split(text, mode)


async def analyze_sentence(sentence: str, variant: str, sentence_index: int) -> dict:
    return await _analyzer.analyze_sentence(sentence, variant, sentence_index)


async def analyze_text(text: str, variant: str, mode: str = "plain"):
    async for r in _analyzer.analyze_text(text, variant, mode):
        yield r
