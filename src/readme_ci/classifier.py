"""Heuristic classification of extracted snippets.

Decides what readme-ci may eventually do with a snippet. Deliberately
conservative: anything ambiguous is kept away from the "runnable" bucket.
Nothing in this module executes anything.

Categories:
    runnable              safe to attempt inside the sandbox (when it exists)
    unsupported-language  language readme-ci does not know how to run
    placeholder           contains fill-me-in tokens; illustrative, not executable
    unsafe                destructive or host-touching patterns; never run
    needs-network         would require network/external services (sandbox is offline)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .extractor import Snippet

RUNNABLE = "runnable"
UNSUPPORTED = "unsupported-language"
PLACEHOLDER = "placeholder"
UNSAFE = "unsafe"
NEEDS_NETWORK = "needs-network"
DIRECTIVE_SKIP = "directive-skip"

#: Languages the (future) sandbox knows how to run, normalized.
SUPPORTED_LANGS = {
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "python": "python",
    "python3": "python",
    "py": "python",
}

_PLACEHOLDER_RES = [
    re.compile(r"<[A-Za-z][A-Za-z0-9 _.-]*>"),  # <your-project>, <API TOKEN>
    re.compile(r"\bYOUR_[A-Z0-9_]+\b"),
    re.compile(r"\byour-[a-z0-9-]+\b"),
    re.compile(r"^\s*\.\.\.\s*$", re.MULTILINE),  # bare ellipsis line
    re.compile(r"\bxxx+\b", re.IGNORECASE),
]

_UNSAFE_BASH_RES = [
    re.compile(r"\brm\b"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\b"),
    re.compile(r">\s*/dev/"),
    re.compile(r"\b(shutdown|reboot|halt)\b"),
    re.compile(r"\bkill(all)?\b"),
    re.compile(r"\bchmod\b\s+-R"),
    re.compile(r"\bchown\b"),
    re.compile(r"\beval\b"),
    re.compile(r"curl[^|\n]*\|\s*(ba|z)?sh"),  # pipe-to-shell
    re.compile(r"wget[^|\n]*\|\s*(ba|z)?sh"),
    re.compile(r":\(\)\s*\{"),  # fork bomb
]

_UNSAFE_PYTHON_RES = [
    re.compile(r"\bos\.system\b"),
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bshutil\.rmtree\b"),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\b__import__\b"),
]

_NETWORK_BASH_RES = [
    re.compile(r"\bcurl\b"),
    re.compile(r"\bwget\b"),
    re.compile(r"\bgit\s+(clone|pull|fetch|push)\b"),
    re.compile(r"\bpip3?\s+install\b"),
    re.compile(r"\b(npm|npx|yarn|pnpm)\b"),
    re.compile(r"\b(apt|apt-get|dnf|yum|brew|apk)\b"),
    re.compile(r"\b(docker|podman|kubectl|helm|terraform)\b"),
    re.compile(r"\bssh\b"),
]

_NETWORK_PYTHON_RES = [
    re.compile(r"\brequests\b"),
    re.compile(r"\burllib\b"),
    re.compile(r"\bhttp\.client\b"),
    re.compile(r"\bsocket\b"),
    re.compile(r"\bhttpx\b"),
]


@dataclass
class Classification:
    category: str
    reason: str


def _first_match(code: str, patterns: list[re.Pattern]) -> str | None:
    for pattern in patterns:
        found = pattern.search(code)
        if found:
            return found.group(0).strip()
    return None


def classify(snippet: Snippet) -> Classification:
    """Classify *snippet* without executing anything."""
    # An explicit author directive wins over everything else.
    if snippet.skip:
        return Classification(DIRECTIVE_SKIP, "readme-ci:skip directive")

    lang = SUPPORTED_LANGS.get(snippet.lang)
    if lang is None:
        shown = snippet.lang or "none"
        return Classification(UNSUPPORTED, f"language: {shown}")

    hit = _first_match(snippet.code, _PLACEHOLDER_RES)
    if hit:
        return Classification(PLACEHOLDER, f"contains placeholder: {hit!r}")

    unsafe_res = _UNSAFE_BASH_RES if lang == "bash" else _UNSAFE_PYTHON_RES
    hit = _first_match(snippet.code, unsafe_res)
    if hit:
        return Classification(UNSAFE, f"matched pattern: {hit!r}")

    network_res = _NETWORK_BASH_RES if lang == "bash" else _NETWORK_PYTHON_RES
    hit = _first_match(snippet.code, network_res)
    if hit:
        return Classification(NEEDS_NETWORK, f"matched pattern: {hit!r}")

    return Classification(RUNNABLE, "no blocking pattern found")
