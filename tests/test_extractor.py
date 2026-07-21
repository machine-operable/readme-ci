"""Tests for the Markdown fenced-block extractor."""

from doc_ci.extractor import extract_snippets


def test_basic_backtick_fence():
    text = "intro\n\n```bash\necho hello\n```\n\noutro\n"
    snips = extract_snippets(text, path="x.md")
    assert len(snips) == 1
    s = snips[0]
    assert s.lang == "bash"
    assert s.code == "echo hello\n"
    assert s.start_line == 3
    assert s.end_line == 5
    assert s.path == "x.md"


def test_tilde_fence():
    text = "~~~python\nprint(1)\n~~~\n"
    snips = extract_snippets(text)
    assert len(snips) == 1
    assert snips[0].lang == "python"
    assert snips[0].code == "print(1)\n"


def test_no_language_fence():
    text = "```\nplain text\n```\n"
    snips = extract_snippets(text)
    assert len(snips) == 1
    assert snips[0].lang == ""


def test_info_string_extra_words():
    text = "```python title=example.py\nx = 1\n```\n"
    snips = extract_snippets(text)
    assert snips[0].lang == "python"


def test_language_is_lowercased():
    text = "```Bash\nls\n```\n"
    snips = extract_snippets(text)
    assert snips[0].lang == "bash"


def test_multiple_snippets():
    text = "```bash\na\n```\n\ntext\n\n```python\nb\n```\n"
    snips = extract_snippets(text)
    assert [s.lang for s in snips] == ["bash", "python"]


def test_longer_closing_fence_allowed():
    text = "```js\ncode\n`````\n"
    snips = extract_snippets(text)
    assert len(snips) == 1
    assert snips[0].code == "code\n"


def test_shorter_fence_does_not_close():
    text = "````\ncontains ``` inside\n````\n"
    snips = extract_snippets(text)
    assert len(snips) == 1
    assert "```" in snips[0].code


def test_unclosed_fence_runs_to_eof():
    text = "```bash\necho unterminated\n"
    snips = extract_snippets(text)
    assert len(snips) == 1
    assert snips[0].code == "echo unterminated\n"
    assert snips[0].end_line == 2


def test_indented_four_spaces_is_not_a_fence():
    text = "    ```bash\n    not a fence\n"
    snips = extract_snippets(text)
    assert snips == []


def test_backtick_info_string_with_backtick_is_not_a_fence():
    text = "``` `code` ```\n"
    snips = extract_snippets(text)
    # inline-code-like line, not an opening fence per CommonMark
    assert snips == [] or snips[0].start_line != 1


def test_empty_snippet():
    text = "```bash\n```\n"
    snips = extract_snippets(text)
    assert len(snips) == 1
    assert snips[0].code == ""


def test_crlf_tolerance():
    text = "```bash\r\necho hi\r\n```\r\n"
    snips = extract_snippets(text)
    assert len(snips) == 1
    assert "echo hi" in snips[0].code


def test_info_string_captured():
    text = "```python title=example.py\nx = 1\n```\n"
    snips = extract_snippets(text)
    assert snips[0].info == "python title=example.py"
    assert snips[0].lang == "python"


def test_no_skip_by_default():
    text = "```bash\necho hi\n```\n"
    assert extract_snippets(text)[0].skip is False


def test_skip_directive_in_info_string():
    text = "```bash doc-ci:skip\necho hi\n```\n"
    snips = extract_snippets(text)
    assert snips[0].skip is True
    assert snips[0].lang == "bash"  # lang still parsed as first token


def test_skip_directive_in_preceding_html_comment():
    text = "<!-- doc-ci:skip -->\n```bash\necho hi\n```\n"
    snips = extract_snippets(text)
    assert snips[0].skip is True


def test_skip_directive_tolerates_space_after_colon():
    text = "```bash doc-ci: skip\necho hi\n```\n"
    assert extract_snippets(text)[0].skip is True


def test_skip_directive_case_insensitive():
    text = "```bash DOC-CI:SKIP\necho hi\n```\n"
    assert extract_snippets(text)[0].skip is True


def test_directive_two_lines_above_does_not_apply():
    # Only the immediately preceding line counts, to stay predictable.
    text = "<!-- doc-ci:skip -->\n\n```bash\necho hi\n```\n"
    assert extract_snippets(text)[0].skip is False
