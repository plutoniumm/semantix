from backend.analyzer import LaTeXPreprocessor, split_sentences

pre = LaTeXPreprocessor()


def test_extracts_document_body():
    text = "\\documentclass{article}\\begin{document}Hello world.\\end{document}"
    assert pre.preprocess(text) == "Hello world."


def test_strips_math_environments():
    text = "Before.\n\\begin{equation}\ne = mc^2\n\\end{equation}\nAfter."
    out = pre.preprocess(text)
    assert "mc^2" not in out
    assert "Before." in out and "After." in out


def test_strips_inline_and_display_math():
    out = pre.preprocess("The value $x + y$ and \\[a = b\\] and $$c$$ end.")
    for frag in ("x + y", "a = b", "$$"):
        assert frag not in out


def test_strips_comments_but_not_escaped_percent():
    out = pre.preprocess("Keep 50\\% of this. % drop this comment")
    assert "50" in out
    assert "drop this" not in out


def test_expands_formatting_commands():
    out = pre.preprocess("We use \\textbf{bold} and \\emph{emphasis} here.")
    assert "bold" in out and "emphasis" in out
    assert "\\textbf" not in out


def test_keeps_captions_drops_includegraphics():
    text = (
        "\\begin{figure}\\includegraphics[width=1cm]{img.png}"
        "\\caption{A nice caption}\\end{figure}"
    )
    out = pre.preprocess(text)
    assert "A nice caption" in out
    assert "img.png" not in out


def test_removes_citations_and_replaces_refs():
    out = pre.preprocess("As shown~\\cite{smith2020}, see Section~\\ref{sec:x}.")
    assert "smith2020" not in out
    assert "sec:x" not in out


def test_has_residual_latex():
    assert LaTeXPreprocessor.has_residual_latex("still has \\foo here")
    assert not LaTeXPreprocessor.has_residual_latex("clean prose only")


def test_split_filters_short_sentences():
    result = split_sentences("Hi. This sentence is long enough to keep.")
    assert result == ["This sentence is long enough to keep."]


def test_split_empty_text():
    assert split_sentences("") == []
    assert split_sentences("   \n  ") == []


def test_split_latex_mode_drops_residual_latex_sentences():
    text = (
        "\\begin{document}This clean sentence stays here. "
        "\\badmacro{arg1}{arg2} unknown \\weird{x} tokens remain maybe.\\end{document}"
    )
    result = split_sentences(text, mode="latex")
    assert "This clean sentence stays here." in result
