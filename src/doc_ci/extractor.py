"""Extract fenced code snippets from Markdown text.

CommonMark-style fenced code blocks only: opening fence of three or more
backticks or tildes (indented at most three spaces), optional info string
whose first word is treated as the language, closed by a fence of the same
character at least as long as the opener. Unclosed fences run to end of file,
matching how most renderers display them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Snippet:
    """One fenced code block found in a Markdown document."""

    path: str
    lang: str
    code: str
    start_line: int  # 1-based line number of the opening fence
    end_line: int  # 1-based line number of the closing fence (or last line if unclosed)

    def to_dict(self) -> dict:
        return asdict(self)


def _fence_open(line: str) -> tuple[str, int, str] | None:
    """Return (fence_char, fence_length, info_string) if *line* opens a fence."""
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return None  # indented 4+ spaces: an indented code block, not a fence
    for ch in ("`", "~"):
        if stripped.startswith(ch * 3):
            length = len(stripped) - len(stripped.lstrip(ch))
            info = stripped[length:].strip()
            # CommonMark: an info string on a backtick fence may not contain backticks
            if ch == "`" and "`" in info:
                return None
            return ch, length, info
    return None


def _fence_close(line: str, ch: str, min_len: int) -> bool:
    """Return True if *line* closes a fence opened with *ch* × *min_len*."""
    stripped = line.strip()
    if len(line) - len(line.lstrip(" ")) > 3:
        return False
    return (
        len(stripped) >= min_len
        and stripped == ch * len(stripped)
    )


def extract_snippets(text: str, path: str = "<string>") -> list[Snippet]:
    """Extract all fenced code snippets from Markdown *text*."""
    snippets: list[Snippet] = []
    lines = text.splitlines()

    in_fence = False
    fence_char = ""
    fence_len = 0
    lang = ""
    buf: list[str] = []
    start_line = 0
    last_line = 0

    for lineno, line in enumerate(lines, start=1):
        last_line = lineno
        if not in_fence:
            opened = _fence_open(line)
            if opened is not None:
                fence_char, fence_len, info = opened
                lang = info.split()[0].lower() if info else ""
                in_fence = True
                buf = []
                start_line = lineno
        else:
            if _fence_close(line, fence_char, fence_len):
                snippets.append(
                    Snippet(
                        path=path,
                        lang=lang,
                        code="\n".join(buf) + ("\n" if buf else ""),
                        start_line=start_line,
                        end_line=lineno,
                    )
                )
                in_fence = False
            else:
                buf.append(line)

    if in_fence:  # unclosed fence: treat remainder of file as the snippet
        snippets.append(
            Snippet(
                path=path,
                lang=lang,
                code="\n".join(buf) + ("\n" if buf else ""),
                start_line=start_line,
                end_line=last_line,
            )
        )

    return snippets
