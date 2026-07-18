import json
import asyncio
import re
import nltk
import httpx
from backend import llm
from backend.cache import cache
from backend.config import get as get_config

nltk.download("punkt_tab", quiet=True)


READ_TIMEOUT = 120.0
MIN_WORDS = 3

SYSTEM_PROMPT_TEMPLATE = (
    "You are a professional writing assistant for formal documents. "
    "Analyse the following sentence for grammar, spelling, style, and punctuation errors. "
    "Use {variant} English conventions. "
    "Flag contractions (e.g. don't, it's, they're — expand them in the suggestion, e.g. don't → do not), "
    "colloquialisms (e.g. pretty much, kind of, gonna), "
    "and informal intensifiers (very, really) as style issues. "
    "Return a JSON object only, no prose. Schema: "
    '{{"issues": [{{"type": "grammar|spelling|style|punctuation", '
    '"original_fragment": "...", "suggestion": "...", "explanation": "..."}}]}} '
    'If there are no issues, return {{"issues": []}}.'
)


class LaTeXPreprocessor:
    MATH_ENVS = (
        "align",
        "align*",
        "equation",
        "equation*",
        "gather",
        "gather*",
        "multline",
        "multline*",
        "eqnarray",
        "eqnarray*",
        "displaymath",
    )
    NON_PROSE_ENVS = (
        "algorithm",
        "algorithmic",
        "lstlisting",
        "verbatim",
        "tabular",
        "array",
        "pmatrix",
        "bmatrix",
        "vmatrix",
        "matrix",
    )
    FORMATTING_CMDS = (
        "textit",
        "textbf",
        "emph",
        "texttt",
        "textrm",
        "textsc",
        "text",
        "mbox",
    )
    SECTION_CMDS = (
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "title",
    )
    CITE_CMDS = ("cite", "citep", "citet", "citealt", "nocite")
    REF_CMDS = ("ref", "eqref", "pageref")
    METADATA_CMDS = (
        "label",
        "bibliography",
        "bibliographystyle",
        "newcommand",
        "renewcommand",
        "acmJournal",
        "acmVolume",
        "acmNumber",
        "acmArticle",
        "acmYear",
        "acmDOI",
        "setcopyright",
        "author",
        "affiliation",
        "institution",
        "department",
        "city",
        "country",
        "date",
        "keywords",
        "hspace",
        "vspace",
        "setcounter",
        "addtocounter",
        "usepackage",
        "documentclass",
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
                " ",
                text,
                flags=re.DOTALL,
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
                " ",
                text,
                flags=re.DOTALL,
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


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw


class TextAnalyzer:
    # Matches Ollama's parallel slots (-np 4); more would just queue server-side.
    CONCURRENCY = 4

    def __init__(self):
        self._preprocessor = LaTeXPreprocessor()

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
        model = get_config()["analyzer_model"]
        cached = cache.get(sentence, variant, model)
        if cached is not None:
            return {**cached, "sentence_index": idx, "original": sentence}

        variant_label = "British" if variant == "british" else "American"
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(variant=variant_label)

        try:
            raw = await llm.chat(
                model=model,
                system=system_prompt,
                user=sentence,
                json_mode=True,
                read_timeout=READ_TIMEOUT,
            )
            data = json.loads(_strip_fences(raw))
            issues = data.get("issues", [])
            result = {"issues": issues, "parse_error": False}
            cache.put(sentence, variant, result, model)
            return {**result, "sentence_index": idx, "original": sentence}

        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
            ValueError,
        ):
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

        if not await llm.probe():
            raise RuntimeError("LLM unavailable")

        sem = asyncio.Semaphore(self.CONCURRENCY)

        async def bounded(sentence: str, idx: int) -> dict:
            async with sem:
                return await self.analyze_sentence(sentence, variant, idx)

        tasks = [asyncio.create_task(bounded(s, i)) for i, s in enumerate(sentences)]
        try:
            for fut in asyncio.as_completed(tasks):
                yield await fut
        finally:
            for t in tasks:
                t.cancel()


_analyzer = TextAnalyzer()


def split_sentences(text: str, mode: str = "plain") -> list[str]:
    return _analyzer.split(text, mode)


async def analyze_sentence(sentence: str, variant: str, sentence_index: int) -> dict:
    return await _analyzer.analyze_sentence(sentence, variant, sentence_index)


async def analyze_text(text: str, variant: str, mode: str = "plain"):
    async for r in _analyzer.analyze_text(text, variant, mode):
        yield r


async def probe_llm() -> bool:
    return await llm.probe()
