#!/usr/bin/env python3
"""Build the bilingual Index Update notes from changed package version paths."""

from __future__ import annotations

import re
import sys
from collections import defaultdict


PATH_RE = re.compile(r"^pkg/pkginfo_(?:arm64|amd64)/([^/]+)/_[^@]+@(.+)$")
METADATA_SUFFIX = "@common"


def version_sort(version: str) -> tuple[tuple[int, ...], str]:
    if re.fullmatch(r"\d+(?:\.\d+){1,3}", version):
        return tuple(int(part) for part in version.split(".")), version
    return (), version


def release_notes(paths: list[str]) -> str:
    packages: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        stripped = path.strip()
        if stripped.endswith(METADATA_SUFFIX):
            continue
        match = PATH_RE.fullmatch(stripped)
        if match:
            package, version = match.groups()
            packages[package].add(version)
    if not packages:
        raise ValueError("the merged pull request contains no package version records")

    entries = [
        f"`{name} ({', '.join(sorted(versions, key=version_sort))})`"
        for name, versions in sorted(packages.items())
    ]
    package_list = " ".join(entries)
    return (
        "# Index Update 索引更新\n\n"
        f"Add new versions of packages: {package_list}\n\n"
        f"增加软件包的新版本：{package_list}\n\n"
        "由于`wave install`会自动拉取最新数据，你无需手动更新\n\n"
        "Because of  `wave install` automatically pulls the latest data, you don't need to update manually.\n"
    )


def main() -> int:
    try:
        print(release_notes(sys.stdin.read().splitlines()), end="")
        return 0
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
