#!/usr/bin/env python3
"""Require a matching release tag/version and extract its reviewed changelog."""

import argparse
from pathlib import Path
import re


def release_notes(root: Path, tag: str) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise ValueError(f"Invalid VERSION: {version!r}")
    if tag != f"v{version}":
        raise ValueError(f"Tag {tag!r} does not match VERSION {version!r}")
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = list(re.finditer(r"^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\s*$", text, re.M))
    matches = [i for i, heading in enumerate(headings) if heading.group(1) == version]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one dated changelog entry for {version}")
    index = matches[0]
    start = headings[index].end()
    end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
    body = text[start:end].strip()
    if not body or body.upper() in ("TODO", "TBD"):
        raise ValueError(f"Changelog entry for {version} is empty")
    return body + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    args.output.write_text(release_notes(args.root, args.tag), encoding="utf-8")


if __name__ == "__main__":
    main()
