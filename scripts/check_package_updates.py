#!/usr/bin/env python3
"""Find safe GitHub Release updates and write package index records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHES = ("arm64", "amd64")
MAX_DOWNLOAD_SIZE = 512 * 1024 * 1024
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
VERSION_TAG_PATTERNS = (
    re.compile(r"^v?(\d+(?:\.\d+){1,3})$", re.IGNORECASE),
    re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*[-_]v?(\d+(?:\.\d+){1,3})$", re.IGNORECASE),
)
VERSION_ONLY_RE = re.compile(r"\d+(?:\.\d+){1,3}")
ARCH_PATTERNS = {
    "arm64": re.compile(r"(?<![A-Za-z0-9])(?:arm64|aarch64)(?![A-Za-z0-9])", re.IGNORECASE),
    "amd64": re.compile(r"(?<![A-Za-z0-9])(?:amd64|x86_64|x86-64|x64)(?![A-Za-z0-9])", re.IGNORECASE),
}
LINUX_RE = re.compile(r"(?<![A-Za-z0-9])(?:linux|gnu)(?![A-Za-z0-9])", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def classify_arch(text: str) -> str | None:
    matches = [arch for arch, pattern in ARCH_PATTERNS.items() if pattern.search(text)]
    return matches[0] if len(matches) == 1 else None


def version_tuple(version: str) -> tuple[int, ...] | None:
    if not VERSION_ONLY_RE.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def version_from_tag(tag: str) -> str | None:
    for pattern in VERSION_TAG_PATTERNS:
        match = pattern.fullmatch(tag)
        if match:
            version = match.group(1)
            return version if version_tuple(version) is not None else None
    return None


def parse_github_release_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 5 or parts[2:4] != ["releases", "download"]:
        return None
    return f"{parts[0]}/{parts[1]}"


def github_home_repo(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def parse_record(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r'^([A-Za-z_][A-Za-z_0-9]*):\s*"([^"]*)"\s*$', line)
        if match:
            fields[match.group(1)] = match.group(2)
        elif re.match(r"^deps\s*:", line):
            fields["deps"] = line.partition(":")[2].strip()
    return fields


def latest_record(directory: Path, package: str) -> tuple[str, Path] | None:
    candidates: list[tuple[tuple[int, ...], str, Path]] = []
    prefix = f"_{package}@"
    for path in directory.iterdir():
        if not path.is_file() or not path.name.startswith(prefix):
            continue
        version = path.name[len(prefix) :]
        parsed = version_tuple(version)
        if parsed is not None:
            candidates.append((parsed, version, path))
    if not candidates:
        return None
    _, version, path = max(candidates, key=lambda item: (item[0], item[1]))
    return version, path


def normalized_asset_name(name: str, version: str) -> str:
    normalized = name.lower().replace(version.lower(), "{version}")
    for pattern in ARCH_PATTERNS.values():
        normalized = pattern.sub("{arch}", normalized)
    return normalized


def matching_asset(
    assets: list[dict[str, object]],
    current_url: str,
    old_version: str,
    new_version: str,
    arch: str,
) -> tuple[dict[str, object] | None, str]:
    parsed = urllib.parse.urlparse(current_url)
    old_name = Path(urllib.parse.unquote(parsed.path)).name
    if not old_name:
        return None, "current URL has no asset filename"

    expected = normalized_asset_name(old_name, old_version)
    candidates: list[dict[str, object]] = []
    for asset in assets:
        name = asset.get("name")
        if not isinstance(name, str) or classify_arch(name) != arch or not LINUX_RE.search(name):
            continue
        if normalized_asset_name(name, new_version) == expected:
            candidates.append(asset)

    if len(candidates) == 1:
        return candidates[0], ""
    if not candidates:
        return None, f"no unambiguous {arch} Linux asset matches the existing filename format"
    return None, f"{len(candidates)} {arch} Linux assets match the existing filename format"


def github_json(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "LinuxWave-package-index-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            body = error.read(500).decode("utf-8", errors="replace")
            if error.code < 500 or attempt == RETRY_ATTEMPTS:
                raise RuntimeError(
                    f"GitHub API request failed ({error.code}) for {url}: {body}"
                ) from error
        except urllib.error.URLError as error:
            if attempt == RETRY_ATTEMPTS:
                raise RuntimeError(f"GitHub API request failed for {url}: {error}") from error
        time.sleep(RETRY_DELAY_SECONDS * attempt)
    raise RuntimeError(f"GitHub API request failed for {url}")


def download_sha256(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise RuntimeError(f"refusing to download asset from an untrusted host: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "LinuxWave-package-index-updater"})
    digest = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD_SIZE:
                    raise RuntimeError(f"asset exceeds the {MAX_DOWNLOAD_SIZE}-byte checksum limit: {url}")
                digest.update(chunk)
    except urllib.error.URLError as error:
        raise RuntimeError(f"failed to download asset for checksum: {url}: {error}") from error
    if total == 0:
        raise RuntimeError(f"downloaded an empty asset: {url}")
    return digest.hexdigest()


def asset_sha256(asset: dict[str, object], url: str) -> str:
    digest = asset.get("digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        value = digest.removeprefix("sha256:")
        if SHA256_RE.fullmatch(value):
            return value
        raise RuntimeError(f"GitHub returned an invalid SHA-256 digest for {url}")
    return download_sha256(url)


def is_dependency_record(fields: dict[str, str]) -> bool:
    return "deps" in fields


def report_text(updates: list[dict[str, str]], skipped: list[str]) -> str:
    if updates:
        lines = ["## Candidate package updates", ""]
        for item in updates:
            lines.append(f"- `{item['package']}@{item['version']}` ({item['arch']})")
        lines.append("")
    else:
        lines = ["No safe GitHub Release updates were found.", ""]
    if skipped:
        lines.extend(["<details>", "<summary>Skipped packages</summary>", ""])
        lines.extend(f"- {item}" for item in skipped)
        lines.extend(["", "</details>", ""])
    lines.extend(
        [
            "",
            "Generated by the package-index updater. Please review every version, architecture, URL, and checksum before merging.",
            "",
            "<!-- linuxwave-package-index-updates -->",
            "",
        ]
    )
    return "\n".join(lines)


def discover_updates(root: Path) -> tuple[list[dict[str, str]], list[str]]:
    release_cache: dict[str, object] = {}
    api_failures = 0
    planned: list[dict[str, str]] = []
    skipped: list[str] = []

    for arch in ARCHES:
        arch_dir = root / "pkg" / f"pkginfo_{arch}"
        for package_dir in sorted(arch_dir.iterdir()):
            if not package_dir.is_dir() or package_dir.name.startswith("test_"):
                continue
            package = package_dir.name
            current = latest_record(package_dir, package)
            if current is None:
                skipped.append(f"`{package}` ({arch}): no plain numeric version record to compare")
                continue
            old_version, record_path = current
            fields = parse_record(record_path)
            current_url = fields.get("url", "")
            release_repo = parse_github_release_url(current_url)
            if release_repo is None:
                continue
            if is_dependency_record(fields):
                skipped.append(f"`{package}` ({arch}): dependency metadata needs manual review")
                continue

            common_path = package_dir / f"_{package}@common"
            common = parse_record(common_path) if common_path.exists() else {}
            homepage = common.get("hom", "")
            homepage_url = urllib.parse.urlparse(homepage)
            if homepage_url.scheme != "https" or not homepage_url.hostname:
                skipped.append(f"`{package}` ({arch}): package homepage is missing or not HTTPS")
                continue
            home_repo = github_home_repo(homepage)
            if home_repo is not None and home_repo.casefold() != release_repo.casefold():
                skipped.append(f"`{package}` ({arch}): release repository differs from package homepage")
                continue

            if release_repo not in release_cache:
                try:
                    release_cache[release_repo] = github_json(
                        f"https://api.github.com/repos/{release_repo}/releases/latest"
                    )
                except RuntimeError as error:
                    api_failures += 1
                    skipped.append(f"`{package}` ({arch}): {error}")
                    continue
            release = release_cache[release_repo]
            if release is None:
                skipped.append(f"`{package}` ({arch}): upstream has no published stable GitHub Release")
                continue
            if not isinstance(release, dict):
                skipped.append(f"`{package}` ({arch}): unexpected GitHub Release response for {release_repo}")
                continue
            tag = release.get("tag_name")
            assets = release.get("assets")
            if not isinstance(tag, str) or not isinstance(assets, list):
                skipped.append(f"`{package}` ({arch}): GitHub Release response has no tag/assets for {release_repo}")
                continue
            new_version = version_from_tag(tag)
            if new_version is None:
                skipped.append(f"`{package}` ({arch}): release tag {tag!r} is not a plain numeric version")
                continue
            old_key = version_tuple(old_version)
            new_key = version_tuple(new_version)
            assert old_key is not None and new_key is not None
            if new_key <= old_key:
                continue

            asset, reason = matching_asset(assets, current_url, old_version, new_version, arch)
            if asset is None:
                skipped.append(f"`{package}` ({arch}) {new_version}: {reason}")
                continue
            url = asset.get("browser_download_url")
            if not isinstance(url, str):
                skipped.append(f"`{package}` ({arch}) {new_version}: asset has no browser download URL")
                continue
            parsed_url = urllib.parse.urlparse(url)
            if parsed_url.scheme != "https" or parsed_url.hostname != "github.com":
                skipped.append(f"`{package}` ({arch}) {new_version}: asset URL is not a github.com release URL")
                continue

            version_path = package_dir / f"_{package}@{new_version}"
            if version_path.exists():
                skipped.append(f"`{package}@{new_version}` ({arch}): version record already exists")
                continue
            try:
                digest = asset_sha256(asset, url)
            except RuntimeError as error:
                skipped.append(f"`{package}` ({arch}) {new_version}: {error}")
                continue
            planned.append(
                {
                    "package": package,
                    "version": new_version,
                    "arch": arch,
                    "path": str(version_path.relative_to(root)),
                    "content": f'sha256: "{digest}"\nurl: "{url}"\n',
                    "url": url,
                    "sha256": digest,
                }
            )

    if api_failures and not release_cache:
        raise RuntimeError(
            f"every GitHub API request failed ({api_failures}); check the token and the network"
        )
    return planned, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write discovered records to the index")
    parser.add_argument("--report-file", type=Path, help="write a Markdown report to this path")
    args = parser.parse_args()

    try:
        updates, skipped = discover_updates(ROOT)
        if args.write:
            for item in updates:
                path = ROOT / item["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(item["content"], encoding="utf-8")
                print(f"Added {item['path']}")
        else:
            for item in updates:
                print(f"Candidate {item['path']} {item['sha256']} {item['url']}")
        for item in skipped:
            print(f"Skipped {item}", file=sys.stderr)
        report = report_text(updates, skipped)
        if args.report_file:
            args.report_file.write_text(report, encoding="utf-8")
        if not updates:
            print("No package index changes found.")
        return 0
    except (OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
