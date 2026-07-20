"""Tests for the snippet classifier. Nothing here executes snippet content."""

from doc_ci.classifier import (
    NEEDS_NETWORK,
    PLACEHOLDER,
    RUNNABLE,
    UNSAFE,
    UNSUPPORTED,
    classify,
)
from doc_ci.extractor import Snippet


def snip(code: str, lang: str = "bash") -> Snippet:
    return Snippet(path="x.md", lang=lang, code=code, start_line=1, end_line=2)


def test_plain_echo_is_runnable():
    assert classify(snip("echo hello\n")).category == RUNNABLE


def test_plain_python_print_is_runnable():
    assert classify(snip("print(1 + 1)\n", lang="python")).category == RUNNABLE


def test_unknown_language_is_unsupported():
    assert classify(snip("SELECT 1;\n", lang="sql")).category == UNSUPPORTED


def test_no_language_is_unsupported():
    assert classify(snip("something\n", lang="")).category == UNSUPPORTED


def test_lang_aliases_map_to_supported():
    assert classify(snip("echo hi\n", lang="sh")).category == RUNNABLE
    assert classify(snip("print(1)\n", lang="py")).category == RUNNABLE


def test_angle_bracket_placeholder():
    got = classify(snip("git remote add origin <your-repo-url>\n"))
    assert got.category == PLACEHOLDER


def test_your_underscore_placeholder():
    assert classify(snip("export TOKEN=YOUR_API_TOKEN\n")).category == PLACEHOLDER


def test_bare_ellipsis_line_is_placeholder():
    assert classify(snip("do_setup()\n...\ndo_more()\n", lang="python")).category == PLACEHOLDER


def test_rm_is_unsafe():
    assert classify(snip("rm -rf build/\n")).category == UNSAFE


def test_sudo_is_unsafe():
    assert classify(snip("sudo make install\n")).category == UNSAFE


def test_pipe_to_shell_is_unsafe():
    assert classify(snip("curl -fsSL https://example.com/install.sh | sh\n")).category == UNSAFE


def test_python_subprocess_is_unsafe():
    assert classify(snip("import subprocess\n", lang="python")).category == UNSAFE


def test_pip_install_needs_network():
    assert classify(snip("pip install doc-ci\n")).category == NEEDS_NETWORK


def test_git_clone_needs_network():
    assert classify(snip("git clone https://github.com/x/y\n")).category == NEEDS_NETWORK


def test_python_requests_needs_network():
    assert classify(snip("import requests\n", lang="python")).category == NEEDS_NETWORK


def test_unsafe_wins_over_network():
    # a snippet that both installs and removes: unsafe must win
    got = classify(snip("pip install x && rm -rf /tmp/x\n"))
    assert got.category == UNSAFE


def test_reason_is_informative():
    got = classify(snip("sudo apt-get update\n"))
    assert "sudo" in got.reason
