"""doc-ci command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .extractor import Snippet, extract_snippets


def _collect_files(raw_paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in raw_paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
        else:
            files.append(path)
    return files


def cmd_scan(args: argparse.Namespace) -> int:
    snippets: list[Snippet] = []
    errors = 0
    for file in _collect_files(args.paths):
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"warning: could not read {file}: {exc}", file=sys.stderr)
            errors += 1
            continue
        snippets.extend(extract_snippets(text, path=str(file)))

    if args.json:
        print(json.dumps([s.to_dict() for s in snippets], indent=2))
    else:
        for s in snippets:
            lang = s.lang or "no-lang"
            n = len(s.code.splitlines())
            print(f"{s.path}:{s.start_line}-{s.end_line}  [{lang}]  {n} line(s)")
        print(f"\n{len(snippets)} snippet(s) found")

    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-ci",
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
