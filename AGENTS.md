# AGENTS.md

Instructions for AI coding agents working in this repository. This file is kept accurate against CI — if it contradicts `.github/workflows/ci.yml`, that is a bug; fix whichever is wrong.

## What this project is

`readme-ci` extracts fenced code snippets from Markdown documentation and will (in later versions) execute them in a sandbox to detect broken examples. Python, stdlib-only at runtime.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Test

```bash
pytest
```

All tests must pass before committing. New extractor behavior requires new test cases in `tests/`.

## Run

```bash
readme-ci scan README.md          # human-readable snippet inventory (read-only)
readme-ci scan README.md --json   # machine-readable
readme-ci run README.md           # execute runnable snippets in a sandbox
readme-ci run README.md --json    # machine-readable pass/fail results
```

## Layout

- `src/readme_ci/extractor.py` — Markdown fenced-block extraction (state machine, no regex-only shortcuts, no dependencies)
- `src/readme_ci/classifier.py` — conservative snippet classification (runnable / unsupported-language / placeholder / unsafe / needs-network); never executes anything
- `src/readme_ci/runner.py` — sandboxed execution (`Sandbox` protocol + `DockerSandbox`); only runs `runnable` snippets, and only inside the sandbox
- `src/readme_ci/cli.py` — argparse CLI, `scan` and `run` subcommands
- `tests/` — pytest suite

## Conventions

- Runtime code uses the Python standard library only. Dev dependencies (pytest) go in `[project.optional-dependencies] dev`.
- Type hints on all public functions.
- Supported Python: 3.10+ (CI tests 3.10 and 3.12).

## Hard rule — snippet execution

Do NOT add any code path that executes extracted snippets directly on the host. Execution (when implemented) happens only inside the sandbox design: container, network disabled, timeout, conservative allowlist. Snippets are untrusted input. A PR that shells out to snippet content outside the sandbox will be rejected regardless of tests passing.
