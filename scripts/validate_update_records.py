#!/usr/bin/env python3
"""Validate newly added package version records."""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

from check_package_updates import ARCH_PATTERNS, SHA256_RE


RECORD_RE = re.compile(r"^pkg/pkginfo_(arm64|amd64)/([^/]+)/_([^@]+)@(.+)$")
METADATA_SUFFIX = "@common"
# Fixture packages under test_* are deliberately malformed; the updater skips
# them as well.
TEST_PACKAGE_PREFIX = "test_"

# conda and continuum mirror URLs name the builds "linux-64" and
# "linux-aarch64"/"linux-arm64", which the shared asset-name patterns treat
# ambiguously (both name a platform and an architecture).
MIRROR_ARCH_PATTERNS = (
    ("arm64", re.compile(r"(?<![A-Za-z0-9])linux-(?:aarch64|arm64)(?![A-Za-z0-9])", re.IGNORECASE)),
    ("amd64", re.compile(r"(?<![A-Za-z0-9])linux-64(?![A-Za-z0-9])", re.IGNORECASE)),
)


def url_arch(url: str) -> str | None:
    """Architecture the download URL declares, or None when it declares none."""
    text = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    declared = {arch for arch, pattern in ARCH_PATTERNS.items() if pattern.search(text)}
    declared |= {arch for arch, pattern in MIRROR_ARCH_PATTERNS if pattern.search(text)}
    return declared.pop() if len(declared) == 1 else None


def validate(path: Path) -> list[str]:
    if path.name.endswith(METADATA_SUFFIX):
        return []
    relative = path.as_posix()
    match = RECORD_RE.fullmatch(relative)
    if match is None:
        return [f"{relative}: not a package version record"]

    arch, directory_name, record_name, version = match.groups()
    if directory_name.startswith(TEST_PACKAGE_PREFIX):
        return []
    errors: list[str] = []
    if directory_name != record_name:
        errors.append(f"{relative}: package directory and record name do not match")
    if not version:
        errors.append(f"{relative}: empty version")

    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        field = re.match(r'^([A-Za-z_][A-Za-z_0-9]*):\s*"([^"]*)"\s*$', line)
        if field:
            fields[field.group(1)] = field.group(2)
    digest = fields.get("sha256", "")
    if not SHA256_RE.fullmatch(digest):
        errors.append(f"{relative}: sha256 must be 64 lowercase hexadecimal characters")
    url = fields.get("url", "")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        errors.append(f"{relative}: URL must be HTTPS")
    else:
        upstream_file = fields.get("file", "")
        expected_name = Path(urllib.parse.unquote(parsed.path)).name
        if not upstream_file:
            errors.append(
                f"{relative}: file must record the upstream asset filename "
                f"(expected {expected_name!r})"
            )
        elif "/" in upstream_file:
            errors.append(f"{relative}: file must be a bare filename, not a path")
        elif expected_name and upstream_file != expected_name:
            errors.append(
                f"{relative}: file is {upstream_file!r} but the URL names {expected_name!r}"
            )
        declared = url_arch(url)
        if declared is not None and declared != arch:
            errors.append(
                f"{relative}: URL identifies the {declared} architecture but the record is {arch}"
            )
    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: validate_update_records.py <new-record> [...]", file=sys.stderr)
        return 2
    errors = [error for arg in sys.argv[1:] for error in validate(Path(arg))]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Validated {len(sys.argv) - 1} new package version record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
