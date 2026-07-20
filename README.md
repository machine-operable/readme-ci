# doc-ci

**Test the code examples in your documentation — automatically, in CI.**

The examples in a project's README are the first thing humans and AI assistants copy, and almost nobody tests them after writing them. The software changes, the examples don't, and they quietly break. doc-ci finds the code snippets in your Markdown documentation and (soon) executes them in a sealed sandbox, so "our examples always run" can be a CI-enforced promise instead of a hope.

## Status

**v0.0.1 in progress — early and honest about it.**

| Stage | Status |
|---|---|
| Extract fenced code snippets from Markdown | ✅ works |
| Classify snippets (runnable vs. illustrative) | ⏳ next |
| Execute snippets in a network-isolated sandbox | ⏳ planned |
| Pass/fail report + CI gate | ⏳ planned |

Nothing is executed yet. Today doc-ci only *reads* your docs and inventories the snippets in them.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
doc-ci scan README.md
```

`scan` lists every fenced code block it finds, with language and line numbers:

```
README.md:22-26  [bash]  3 line(s)
...
```

Add `--json` for machine-readable output.

## Safety design (the rule that governs this project)

Documentation snippets are untrusted input. When execution lands, it will be:

- **Sandboxed** — containers with networking disabled and strict timeouts
- **Conservative** — snippets containing destructive patterns (`rm`, `sudo`, pipe-to-shell, credential placeholders like `YOUR_API_KEY`) are classified as non-runnable and skipped
- **Opt-in** — nothing runs outside the sandbox, ever, and nothing runs at all unless you ask

## Why this exists

doc-ci is the first tool from [machine-operable](https://github.com/machine-operable), a research program measuring — and fixing — how reliably open source repositories work for the humans and AI agents that depend on them. Broken documentation examples don't just mislead newcomers anymore; they get learned and repeated by AI assistants at scale.

## License

[Apache-2.0](LICENSE)
