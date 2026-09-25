# readme-ci

**Test the code examples in your documentation — automatically, in CI.**

The examples in a project's README are the first thing humans and AI assistants copy, and almost nobody tests them after writing them. The software changes, the examples don't, and they quietly break. readme-ci finds the code snippets in your Markdown documentation and executes the runnable ones in a sealed sandbox, so "our examples always run" can be a CI-enforced promise instead of a hope.

## Status

**v0.0.1 in progress — early and honest about it.**

| Stage | Status |
|---|---|
| Extract fenced code snippets from Markdown | ✅ works |
| Classify snippets (runnable / placeholder / unsafe / needs-network) | ✅ heuristic v0 |
| Execute snippets in a network-isolated Docker sandbox | ✅ implemented |
| Pass/fail report + CI gate | ✅ `readme-ci run` |

`readme-ci scan` only *reads* your docs (no execution). `readme-ci run` executes the
snippets classified as runnable — but only inside a locked-down Docker sandbox.
When no sandbox is available, runnable snippets are reported as skipped: readme-ci
never falls back to running untrusted code on the host.

## Quick start

Install from PyPI:

```bash readme-ci:skip
pip install readme-ci
readme-ci scan README.md
```

Or from source, for development:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
readme-ci scan README.md
```

`scan` lists every fenced code block it finds, with language, line numbers, and a conservative classification:

```
README.md:22-26  [bash]  3 line(s)  needs-network
```

To actually execute the runnable examples (in a sandbox) and get a pass/fail
report suitable for CI:

```bash readme-ci:skip
readme-ci run README.md
readme-ci run docs/ --timeout 20 --json
```

`run` exits non-zero if any snippet fails, so it works as a CI gate. Add
`--json` to either command for machine-readable output.

### Skipping a snippet

An example that shouldn't be executed — it needs a real service, is purely
illustrative, or is intentionally broken — can be marked so `readme-ci run`
leaves it alone, without adding noise to the code readers copy. Either:

- put `readme-ci:skip` in the fence info string, right after the language
  (e.g. an opening fence of `` ```python readme-ci:skip ``), or
- put `<!-- readme-ci:skip -->` on the line immediately above the fence.

The marker never appears in the copyable code, and the snippet is reported as
`directive-skip` instead of being run.

## Safety design (the rule that governs this project)

Documentation snippets are untrusted input. Execution is:

- **Sandboxed** — containers with networking disabled and strict timeouts
- **Conservative** — snippets containing destructive patterns (`rm`, `sudo`, pipe-to-shell, credential placeholders like `YOUR_API_KEY`) are classified as non-runnable and skipped
- **Opt-in** — nothing runs outside the sandbox, ever, and nothing runs at all unless you ask

## Why this exists

readme-ci is the first tool from [Machine-Operable Open Source](https://machine-operable.org/) ([GitHub](https://github.com/machine-operable)), a research program measuring — and fixing — how reliably open source repositories work for the humans and AI agents that depend on them. Broken documentation examples don't just mislead newcomers anymore; they get learned and repeated by AI assistants at scale.

## Feedback and background

- Found a snippet readme-ci misclassifies, or an example it runs wrongly? [Open an issue](https://github.com/machine-operable/readme-ci/issues). False positives are bugs.
- Overview of the work and related tools: [machine-operable documentation](https://oss-infrastructure-initiative.netlify.app/machine-operable-documentation) on the OSS Infrastructure Initiative site.
- How the research behind it is done: [method and evidence rules](https://ecogetaway.github.io/method.html).

## License

[Apache-2.0](LICENSE)
