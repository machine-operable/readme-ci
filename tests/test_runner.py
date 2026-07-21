"""Tests for the snippet runner.

These use a FakeSandbox so the orchestration logic is verified without any
dependency on Docker. Nothing here executes real snippet content.
"""

from doc_ci.extractor import Snippet
from doc_ci.runner import (
    ERROR,
    FAILED,
    PASSED,
    SKIPPED,
    DockerSandbox,
    ExecOutcome,
    RunResult,
    run_snippets,
    summarize,
)


def snip(code: str, lang: str = "bash") -> Snippet:
    return Snippet(path="x.md", lang=lang, code=code, start_line=1, end_line=2)


class FakeSandbox:
    """A deterministic stand-in for a real sandbox.

    `script` maps a snippet's code to the ExecOutcome to return. Any code not
    in the script produces a clean exit 0.
    """

    name = "fake"

    def __init__(self, available: bool = True, script: dict | None = None) -> None:
        self._available = available
        self._script = script or {}
        self.calls: list[tuple[str, str]] = []

    def available(self) -> bool:
        return self._available

    def run(self, language: str, code: str, timeout_s: float) -> ExecOutcome:
        self.calls.append((language, code))
        if code in self._script:
            return self._script[code]
        return ExecOutcome(0, "", "", False, 0.01)


def test_runnable_snippet_passes_on_exit_zero():
    box = FakeSandbox()
    results = run_snippets([snip("echo hi\n")], box)
    assert len(results) == 1
    assert results[0].status == PASSED
    assert box.calls == [("bash", "echo hi\n")]


def test_runnable_snippet_fails_on_nonzero_exit():
    box = FakeSandbox(script={"boom\n": ExecOutcome(1, "", "err", False, 0.02)})
    results = run_snippets([snip("boom\n")], box)
    assert results[0].status == FAILED
    assert "exit 1" in results[0].reason


def test_timeout_is_a_failure():
    box = FakeSandbox(script={"sleep 999\n": ExecOutcome(124, "", "", True, 30.0)})
    results = run_snippets([snip("sleep 999\n")], box, timeout_s=30.0)
    assert results[0].status == FAILED
    assert "timed out" in results[0].reason


def test_non_runnable_snippet_is_skipped_not_executed():
    box = FakeSandbox()
    # sudo -> classified unsafe, must never reach the sandbox
    results = run_snippets([snip("sudo rm -rf /\n")], box)
    assert results[0].status == SKIPPED
    assert "unsafe" in results[0].reason
    assert box.calls == []  # never executed


def test_placeholder_snippet_is_skipped():
    box = FakeSandbox()
    results = run_snippets([snip("export T=YOUR_TOKEN\n")], box)
    assert results[0].status == SKIPPED
    assert "placeholder" in results[0].reason
    assert box.calls == []


def test_unsupported_language_is_skipped():
    box = FakeSandbox()
    results = run_snippets([snip("SELECT 1;\n", lang="sql")], box)
    assert results[0].status == SKIPPED
    assert box.calls == []


def test_runnable_snippet_skipped_when_no_sandbox():
    box = FakeSandbox(available=False)
    results = run_snippets([snip("echo hi\n")], box)
    assert results[0].status == SKIPPED
    assert "no sandbox available" in results[0].reason
    assert box.calls == []  # crucial: never falls back to host execution


def test_sandbox_availability_checked_once_not_per_snippet():
    # Even with many snippets, an unavailable sandbox never runs anything.
    box = FakeSandbox(available=False)
    results = run_snippets([snip("echo 1\n"), snip("echo 2\n")], box)
    assert all(r.status == SKIPPED for r in results)
    assert box.calls == []


def test_sandbox_infrastructure_error_becomes_error_status():
    class BrokenSandbox:
        name = "broken"

        def available(self) -> bool:
            return True

        def run(self, language, code, timeout_s):
            raise RuntimeError("daemon exploded")

    results = run_snippets([snip("echo hi\n")], BrokenSandbox())
    assert results[0].status == ERROR
    assert "daemon exploded" in results[0].reason


def test_python_language_normalized_for_sandbox():
    box = FakeSandbox()
    run_snippets([snip("print(1)\n", lang="py")], box)
    assert box.calls == [("python", "print(1)\n")]


def test_mixed_batch_scores_correctly():
    box = FakeSandbox(
        script={
            "fail\n": ExecOutcome(2, "", "", False, 0.01),
        }
    )
    snippets = [
        snip("echo ok\n"),          # passes
        snip("fail\n"),             # fails
        snip("sudo reboot\n"),      # skipped (unsafe)
        snip("SELECT 1\n", "sql"),  # skipped (unsupported)
    ]
    results = run_snippets(snippets, box)
    counts = summarize(results)
    assert counts[PASSED] == 1
    assert counts[FAILED] == 1
    assert counts[SKIPPED] == 2


def test_to_dict_shape():
    box = FakeSandbox()
    result = run_snippets([snip("echo hi\n")], box)[0]
    d = result.to_dict()
    assert d["status"] == PASSED
    assert d["lang"] == "bash"
    assert d["start_line"] == 1
    assert "exit_code" in d and d["exit_code"] == 0


def test_to_dict_without_outcome_omits_exec_fields():
    box = FakeSandbox()
    result = run_snippets([snip("sudo rm\n")], box)[0]  # skipped, no outcome
    d = result.to_dict()
    assert d["status"] == SKIPPED
    assert "exit_code" not in d


def test_summarize_empty():
    assert summarize([]) == {}


# --- DockerSandbox: environment-agnostic checks (no daemon required) ---

def test_docker_available_returns_bool_without_raising():
    # Works whether or not Docker is installed or its daemon is running.
    assert isinstance(DockerSandbox().available(), bool)


def test_docker_missing_binary_is_unavailable_not_crash():
    box = DockerSandbox(docker_bin="doc-ci-no-such-docker-binary-zzz")
    assert box.available() is False


def test_docker_default_images_cover_supported_languages():
    box = DockerSandbox()
    assert "bash" in box.images
    assert "python" in box.images


def test_missing_docker_makes_runnable_snippet_skip_safely():
    # End-to-end: a real DockerSandbox with no docker binary must skip, never run.
    box = DockerSandbox(docker_bin="doc-ci-no-such-docker-binary-zzz")
    results = run_snippets([snip("echo hi\n")], box)
    assert results[0].status == SKIPPED
    assert "no sandbox available" in results[0].reason
