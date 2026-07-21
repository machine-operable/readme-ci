"""readme-ci command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .classifier import classify
from .extractor import Snippet, extract_snippets
from .runner import DockerSandbox, run_snippets, summarize


def _collect_files(raw_paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in raw_paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
        else:
            files.append(path)
    return files


def _gather_snippets(raw_paths: list[str]) -> tuple[list[Snippet], int]:
    """Extract snippets from all given paths. Returns (snippets, read_errors)."""
    snippets: list[Snippet] = []
    errors = 0
    for file in _collect_files(raw_paths):
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"warning: could not read {file}: {exc}", file=sys.stderr)
            errors += 1
            continue
        snippets.extend(extract_snippets(text, path=str(file)))
    return snippets, errors


def cmd_scan(args: argparse.Namespace) -> int:
    snippets, errors = _gather_snippets(args.paths)

    rows = []
    for s in snippets:
        c = classify(s)
        rows.append((s, c))

    if args.json:
        payload = [
            {**s.to_dict(), "category": c.category, "reason": c.reason}
            for s, c in rows
        ]
        print(json.dumps(payload, indent=2))
    else:
        for s, c in rows:
            lang = s.lang or "no-lang"
            n = len(s.code.splitlines())
            print(
                f"{s.path}:{s.start_line}-{s.end_line}  [{lang}]  "
                f"{n} line(s)  {c.category}"
            )
        total = len(rows)
        by_category: dict[str, int] = {}
        for _, c in rows:
            by_category[c.category] = by_category.get(c.category, 0) + 1
        summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_category.items()))
        print(f"\n{total} snippet(s) found" + (f" ({summary})" if summary else ""))

    return 1 if errors else 0


def cmd_run(args: argparse.Namespace) -> int:
    snippets, errors = _gather_snippets(args.paths)
    sandbox = DockerSandbox()
    results = run_snippets(snippets, sandbox, timeout_s=args.timeout)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        _print_run_report(results)

    # CI gate: fail on any failed/errored snippet, or on read errors.
    counts = summarize(results)
    failed = counts.get("failed", 0) + counts.get("error", 0)
    return 1 if (failed or errors) else 0


def _print_run_report(results: list) -> None:
    for r in results:
        lang = r.snippet.lang or "no-lang"
        loc = f"{r.snippet.path}:{r.snippet.start_line}-{r.snippet.end_line}"
        print(f"{r.status.upper():7} {loc}  [{lang}]  {r.reason}")
        # For real failures, show why: the captured error output, indented.
        if r.status in ("failed", "error") and r.outcome is not None:
            detail = (r.outcome.stderr or r.outcome.stdout or "").strip()
            if detail:
                for line in detail.splitlines()[-8:]:
                    print(f"        | {line}")

    counts = summarize(results)
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    verdict = "FAIL" if (counts.get("failed", 0) or counts.get("error", 0)) else "OK"
    print(f"\n[{verdict}] {len(results)} snippet(s)" + (f" — {summary}" if summary else ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="readme-ci",
        description="Test the code examples in your documentation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser(
        "scan",
        help="List the fenced code snippets found in Markdown files",
    )
    scan.add_argument(
        "paths",
        nargs="+",
        help="Markdown files or directories (directories are searched for *.md recursively)",
    )
    scan.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON inventory",
    )
    scan.set_defaults(func=cmd_scan)

    run = sub.add_parser(
        "run",
        help="Execute runnable snippets in a sandbox and report pass/fail",
    )
    run.add_argument(
        "paths",
        nargs="+",
        help="Markdown files or directories (directories are searched for *.md recursively)",
    )
    run.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON results",
    )
    run.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-snippet timeout in seconds (default: 30)",
    )
    run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
