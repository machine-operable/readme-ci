# Changelog

All notable changes to readme-ci are recorded here. This project follows
[semantic versioning](https://semver.org): while on `0.x`, anything may change.

## 0.0.1 — first release

The initial, deliberately small release: readme-ci can find the code examples in
your Markdown documentation, decide which are safe to run, execute those in a
sandbox, and report pass/fail — the complete loop end to end.

### Added

- **Snippet extraction** — finds fenced code blocks in Markdown (CommonMark
  fences, including tilde fences, longer closing fences, unclosed fences, and
  indentation edge cases), recording language and line numbers.
- **Conservative classification** — sorts each snippet into `runnable`,
  `placeholder`, `unsafe`, `needs-network`, or `unsupported-language`. Anything
  ambiguous or destructive is kept away from execution; the unsafe check always
  wins.
- **Sandboxed execution** — `readme-ci run` executes runnable snippets inside a
  locked-down, disposable Docker container (no network, capped memory/CPU/
  processes, all capabilities dropped, read-only root, killed on timeout). When
  no sandbox is available, runnable snippets are skipped — never run on the host.
- **`readme-ci:skip` directive** — mark an example to be left alone, via the fence
  info string or an HTML comment on the preceding line, without adding noise to
  the code readers copy.
- **`scan` and `run` commands** — `scan` inventories and classifies snippets
  (read-only); `run` executes them, shows captured error output for failures,
  and exits non-zero on failure for use as a CI gate. Both support `--json`.
- **Continuous integration** — tested on Python 3.10 and 3.12; the tool is run
  against its own README on every change (dogfooding).
