"""Execute runnable snippets inside a sandbox and report pass/fail.

The safety rule that governs this module: snippet content is untrusted and is
NEVER executed on the host. Execution happens only inside a sandbox that
isolates the network, filesystem, and resources. If no sandbox is available,
runnable snippets are reported as skipped — the tool refuses to fall back to
unsafe host execution.

The orchestration (which snippets to attempt, how to score outcomes) is kept
independent of any particular sandbox via the `Sandbox` protocol, so it can be
tested without Docker.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Protocol

from .classifier import RUNNABLE, SUPPORTED_LANGS, classify
from .extractor import Snippet

# Result statuses
PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"
ERROR = "error"

# Per-language interpreter invocation inside the sandbox.
_INTERP = {
    "bash": ["sh", "-c"],
    "python": ["python3", "-c"],
}

# Default sandbox images per language. Small, widely-mirrored bases.
_DEFAULT_IMAGES = {
    "bash": "alpine:3.20",
    "python": "python:3.12-alpine",
}


@dataclass
class ExecOutcome:
    """The raw result of executing one snippet in a sandbox."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float


@dataclass
class RunResult:
    """A snippet's classification-aware execution result."""

    snippet: Snippet
    status: str  # PASSED / FAILED / SKIPPED / ERROR
    reason: str
    outcome: ExecOutcome | None = None

    def to_dict(self) -> dict:
        data = {
            "path": self.snippet.path,
            "lang": self.snippet.lang,
            "start_line": self.snippet.start_line,
            "end_line": self.snippet.end_line,
            "status": self.status,
            "reason": self.reason,
        }
        if self.outcome is not None:
            data["exit_code"] = self.outcome.exit_code
            data["duration_s"] = round(self.outcome.duration_s, 3)
            data["timed_out"] = self.outcome.timed_out
        return data


class Sandbox(Protocol):
    """A sealed environment that runs a snippet without touching the host."""

    name: str

    def available(self) -> bool:
        """Whether this sandbox can currently run anything."""
        ...

    def run(self, language: str, code: str, timeout_s: float) -> ExecOutcome:
        """Execute *code* in *language*, returning its outcome."""
        ...


class DockerSandbox:
    """Runs snippets in a locked-down, disposable Docker container.

    Each snippet gets a fresh container with: no network, capped memory/CPU/
    processes, all capabilities dropped, a read-only root filesystem, and a
    small writable tmpfs. The container is removed on exit and killed on
    timeout so nothing lingers.
    """

    name = "docker"

    def __init__(
        self,
        images: dict[str, str] | None = None,
        docker_bin: str = "docker",
        memory: str = "256m",
        pids_limit: int = 256,
        image_pull_timeout_s: float = 120.0,
    ) -> None:
        self.images = images or dict(_DEFAULT_IMAGES)
        self.docker_bin = docker_bin
        self.memory = memory
        self.pids_limit = pids_limit
        self.image_pull_timeout_s = image_pull_timeout_s

    def available(self) -> bool:
        try:
            result = subprocess.run(
                [self.docker_bin, "info"],
                capture_output=True,
                timeout=15,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def _ensure_image(self, image: str) -> str | None:
        """Make sure *image* is present locally. Returns an error string on failure."""
        inspect = subprocess.run(
            [self.docker_bin, "image", "inspect", image],
            capture_output=True,
        )
        if inspect.returncode == 0:
            return None
        try:
            pull = subprocess.run(
                [self.docker_bin, "pull", image],
                capture_output=True,
                text=True,
                timeout=self.image_pull_timeout_s,
            )
        except subprocess.TimeoutExpired:
            return f"timed out pulling image {image}"
        if pull.returncode != 0:
            return f"could not pull image {image}: {pull.stderr.strip()[:200]}"
        return None

    def run(self, language: str, code: str, timeout_s: float) -> ExecOutcome:
        image = self.images[language]
        interp = _INTERP[language]
        container = f"docci-{uuid.uuid4().hex[:12]}"
        cmd = [
            self.docker_bin, "run", "--rm",
            "--name", container,
            "--network=none",
            f"--memory={self.memory}",
            f"--memory-swap={self.memory}",  # equal to memory disables swap
            "--cpus=1",
            f"--pids-limit={self.pids_limit}",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:size=32m,exec",
            "--workdir", "/tmp",
            image, *interp, code,
        ]
        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s
            )
        except subprocess.TimeoutExpired as exc:
            # The docker client was killed; make sure the container is too.
            subprocess.run(
                [self.docker_bin, "kill", container],
                capture_output=True,
            )
            duration = time.monotonic() - start
            return ExecOutcome(
                exit_code=124,
                stdout=_as_text(exc.stdout),
                stderr=_as_text(exc.stderr) + f"\n[readme-ci] killed after {timeout_s}s",
                timed_out=True,
                duration_s=duration,
            )
        duration = time.monotonic() - start
        return ExecOutcome(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=False,
            duration_s=duration,
        )


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def run_snippets(
    snippets: list[Snippet],
    sandbox: Sandbox,
    *,
    timeout_s: float = 30.0,
) -> list[RunResult]:
    """Classify each snippet and, if runnable and a sandbox is available, run it.

    Non-runnable snippets are skipped with their classification reason. Runnable
    snippets are skipped when no sandbox is available — never run on the host.
    """
    sandbox_ready = sandbox.available()
    results: list[RunResult] = []

    for snippet in snippets:
        verdict = classify(snippet)
        if verdict.category != RUNNABLE:
            results.append(
                RunResult(snippet, SKIPPED, f"{verdict.category}: {verdict.reason}")
            )
            continue

        if not sandbox_ready:
            results.append(
                RunResult(snippet, SKIPPED, f"no sandbox available ({sandbox.name})")
            )
            continue

        language = SUPPORTED_LANGS[snippet.lang]
        try:
            outcome = sandbox.run(language, snippet.code, timeout_s)
        except Exception as exc:  # sandbox infrastructure failure, not a test failure
            results.append(
                RunResult(snippet, ERROR, f"sandbox error: {exc}", None)
            )
            continue

        if outcome.timed_out:
            results.append(
                RunResult(snippet, FAILED, f"timed out after {timeout_s}s", outcome)
            )
        elif outcome.exit_code == 0:
            results.append(RunResult(snippet, PASSED, "exit 0", outcome))
        else:
            results.append(
                RunResult(snippet, FAILED, f"exit {outcome.exit_code}", outcome)
            )

    return results


def summarize(results: list[RunResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts
