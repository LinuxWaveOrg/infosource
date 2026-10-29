#!/usr/bin/env python3
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_index_release import release_notes
from check_package_updates import (
    classify_arch,
    discover_updates,
    matching_asset,
    LINUX_RE,
    parse_github_release_url,
    version_from_tag,
    version_tuple,
)
from validate_update_records import validate


class PackageUpdateTests(unittest.TestCase):
    def test_architecture_keywords(self):
        self.assertEqual(classify_arch("bat-v1.2-aarch64-apple-linux.tar.gz"), "arm64")
        self.assertEqual(classify_arch("fzf-1.2-linux_arm64.tar.gz"), "arm64")
        self.assertEqual(classify_arch("tool-linux-x86_64.zip"), "amd64")
        self.assertEqual(classify_arch("tool-linux-amd64"), "amd64")
        self.assertIsNone(classify_arch("tool-universal-linux.zip"))
        self.assertIsNone(classify_arch("tool-arm64-x86_64-linux.zip"))
        self.assertEqual(classify_arch("tool-linux-aarch64.tar.gz"), "arm64")
        self.assertIsNotNone(LINUX_RE.search("bat-v0.26.1-aarch64-unknown-linux-musl.tar.gz"))
        self.assertIsNotNone(LINUX_RE.search("jq-linux-amd64"))

    def test_version_parsing_is_conservative(self):
        self.assertEqual(version_from_tag("v1.2.3"), "1.2.3")
        self.assertEqual(version_from_tag("jq-1.8.3"), "1.8.3")
        self.assertEqual(version_from_tag("3.1.738"), "3.1.738")
        self.assertIsNone(version_from_tag("v1.0-linuxwaveteam2"))
        self.assertEqual(version_tuple("1.2.3"), (1, 2, 3))
        self.assertIsNone(version_tuple("1.2.3-procursus7"))

    def test_only_github_release_urls_are_supported(self):
        self.assertEqual(
            parse_github_release_url(
                "https://github.com/junegunn/fzf/releases/download/v1.2/fzf-linux_arm64.tar.gz"
            ),
            "junegunn/fzf",
        )
        self.assertIsNone(parse_github_release_url("https://raw.githubusercontent.com/a/b/v1/file"))
        self.assertIsNone(parse_github_release_url("http://github.com/a/b/releases/download/v1/file"))

    def test_asset_matching_uses_architecture_and_existing_filename_shape(self):
        assets = [
            {"name": "fzf-0.74.6-linux_amd64.tar.gz"},
            {"name": "fzf-0.74.6-linux_arm64.tar.gz"},
            {"name": "fzf-0.74.6-linux_universal.tar.gz"},
            {"name": "fzf-0.74.6-linux_arm64.tar.gz.sha256"},
        ]
        old_url = "https://github.com/junegunn/fzf/releases/download/v0.74.5/fzf-0.74.5-linux_arm64.tar.gz"
        match, reason = matching_asset(assets, old_url, "0.74.5", "0.74.6", "arm64")
        self.assertEqual(match["name"], "fzf-0.74.6-linux_arm64.tar.gz")
        self.assertEqual(reason, "")
        match, _ = matching_asset(assets, old_url, "0.74.5", "0.74.6", "amd64")
        self.assertEqual(match["name"], "fzf-0.74.6-linux_amd64.tar.gz")

    def test_ambiguous_asset_set_is_rejected(self):
        assets = [
            {"name": "tool-2.1-linux-arm64.tar.gz"},
            {"name": "tool-2.1-linux-arm64.tar.gz"},
        ]
        old_url = "https://github.com/example/tool/releases/download/v2.0/tool-2.0-linux-arm64.tar.gz"
        match, reason = matching_asset(assets, old_url, "2.0", "2.1", "arm64")
        self.assertIsNone(match)
        self.assertIn("2 arm64", reason)

    def test_versionless_asset_names_can_match_exactly(self):
        assets = [{"name": "jq-linux-arm64"}]
        old_url = "https://github.com/jqlang/jq/releases/download/jq-1.8.2/jq-linux-arm64"
        match, reason = matching_asset(assets, old_url, "1.8.2", "1.9.0", "arm64")
        self.assertEqual(match["name"], "jq-linux-arm64")
        self.assertEqual(reason, "")

    def test_discovery_creates_records_for_both_architectures(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            digest = "a" * 64
            old_digest = "b" * 64
            assets = []
            for arch, asset_arch in (("arm64", "arm64"), ("amd64", "x86_64")):
                package_dir = root / "pkg" / f"pkginfo_{arch}" / "tool"
                package_dir.mkdir(parents=True)
                (package_dir / "_tool@1.2.0").write_text(
                    f'sha256: "{old_digest}"\n'
                    f'url: "https://github.com/example/tool/releases/download/v1.2.0/tool-1.2.0-linux-{asset_arch}.zip"\n',
                    encoding="utf-8",
                )
                (package_dir / "_tool@common").write_text(
                    'hom: "https://github.com/example/tool"\n',
                    encoding="utf-8",
                )
                asset_name = f"tool-1.3.0-linux-{asset_arch}.zip"
                assets.append(
                    {
                        "name": asset_name,
                        "digest": f"sha256:{digest}",
                        "browser_download_url": (
                            f"https://github.com/example/tool/releases/download/v1.3.0/{asset_name}"
                        ),
                    }
                )

            release = {"tag_name": "v1.3.0", "assets": assets}
            with patch("check_package_updates.github_json", return_value=release) as fetch:
                updates, skipped = discover_updates(root)

        self.assertEqual(
            {(item["package"], item["version"], item["arch"]) for item in updates},
            {("tool", "1.3.0", "arm64"), ("tool", "1.3.0", "amd64")},
        )
        self.assertEqual(skipped, [])
        fetch.assert_called_once()

    def test_one_failing_package_does_not_abort_the_run(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "pkg" / "pkginfo_amd64").mkdir(parents=True)
            digest = "b" * 64
            for name in ("broken", "fine"):
                package_dir = root / "pkg" / "pkginfo_arm64" / name
                package_dir.mkdir(parents=True)
                (package_dir / f"_{name}@1.2.0").write_text(
                    f'sha256: "{digest}"\n'
                    f'url: "https://github.com/example/{name}/releases/download/v1.2.0/'
                    f'{name}-1.2.0-linux-arm64.zip"\n',
                    encoding="utf-8",
                )
                (package_dir / f"_{name}@common").write_text(
                    f'hom: "https://github.com/example/{name}"\n', encoding="utf-8"
                )

            def fake_github_json(url: str) -> object:
                if "/example/broken/" in url:
                    raise RuntimeError("simulated transient failure")
                return {
                    "tag_name": "v1.3.0",
                    "assets": [
                        {
                            "name": "fine-1.3.0-linux-arm64.zip",
                            "digest": f"sha256:{'a' * 64}",
                            "browser_download_url": (
                                "https://github.com/example/fine/releases/download/"
                                "v1.3.0/fine-1.3.0-linux-arm64.zip"
                            ),
                        }
                    ],
                }

            with patch("check_package_updates.github_json", side_effect=fake_github_json):
                updates, skipped = discover_updates(root)

        self.assertEqual([(item["package"], item["version"]) for item in updates], [("fine", "1.3.0")])
        self.assertEqual(len(skipped), 1)
        self.assertIn("broken", skipped[0])
        self.assertIn("simulated transient failure", skipped[0])

    def test_a_total_api_outage_still_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "pkg" / "pkginfo_amd64").mkdir(parents=True)
            package_dir = root / "pkg" / "pkginfo_arm64" / "tool"
            package_dir.mkdir(parents=True)
            (package_dir / "_tool@1.2.0").write_text(
                f'sha256: "{"b" * 64}"\n'
                'url: "https://github.com/example/tool/releases/download/v1.2.0/tool-1.2.0-linux-arm64.zip"\n',
                encoding="utf-8",
            )
            (package_dir / "_tool@common").write_text(
                'hom: "https://github.com/example/tool"\n', encoding="utf-8"
            )
            with patch("check_package_updates.github_json", side_effect=RuntimeError("outage")):
                with self.assertRaises(RuntimeError):
                    discover_updates(root)


class IndexReleaseNotesTests(unittest.TestCase):
    def test_metadata_records_are_not_versions(self):
        notes = release_notes(
            [
                "pkg/pkginfo_arm64/tool/_tool@1.3.0",
                "pkg/pkginfo_amd64/tool/_tool@1.3.0",
                "pkg/pkginfo_arm64/tool/_tool@common",
                "README.md",
            ]
        )
        self.assertIn("`tool (1.3.0)`", notes)
        self.assertNotIn("common", notes)

    def test_notes_are_bilingual(self):
        notes = release_notes(["pkg/pkginfo_arm64/jq/_jq@1.9.0"])
        self.assertIn("Index Update", notes)
        self.assertIn("增加软件包的新版本", notes)

    def test_only_metadata_paths_are_an_error(self):
        with self.assertRaises(ValueError):
            release_notes(["pkg/pkginfo_arm64/tool/_tool@common"])


class UpdateRecordValidationTests(unittest.TestCase):
    def setUp(self):
        self._previous_directory = os.getcwd()
        self._temporary_directory = tempfile.TemporaryDirectory()
        os.chdir(self._temporary_directory.name)

    def tearDown(self):
        os.chdir(self._previous_directory)
        self._temporary_directory.cleanup()

    def write_record(self, relative: str, text: str) -> Path:
        path = Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_metadata_records_are_not_version_records(self):
        path = self.write_record(
            "pkg/pkginfo_arm64/tool/_tool@common", 'hom: "https://example.com"\n'
        )
        self.assertEqual(validate(path), [])

    def test_fixture_packages_are_not_validated(self):
        path = self.write_record(
            "pkg/pkginfo_arm64/test_no_sha256/_test_no_sha256@1.0.0",
            'url: "https://raw.githubusercontent.com/LinuxWaveOrg/LinuxWave/main/test_no_sha256"\n',
        )
        self.assertEqual(validate(path), [])

    def test_conda_style_architecture_in_the_url_path_is_accepted(self):
        path = self.write_record(
            "pkg/pkginfo_amd64/tree/_tree@2.2.1",
            f'sha256: "{"a" * 64}"\n'
            'file: "tree-2.2.1-h6e16a3a_0.conda"\n'
            'url: "https://conda.anaconda.org/conda-forge/linux-64/tree-2.2.1-h6e16a3a_0.conda"\n',
        )
        self.assertEqual(validate(path), [])

    def test_record_without_file_is_rejected(self):
        path = self.write_record(
            "pkg/pkginfo_amd64/tool/_tool@1.3.0",
            f'sha256: "{"c" * 64}"\n'
            'url: "https://github.com/example/tool/releases/download/v1.3.0/tool-linux-amd64.zip"\n',
        )
        errors = validate(path)
        self.assertTrue(errors)
        self.assertIn("file", errors[0])

    def test_file_that_disagrees_with_the_url_is_rejected(self):
        path = self.write_record(
            "pkg/pkginfo_amd64/tool/_tool@1.3.0",
            f'sha256: "{"d" * 64}"\n'
            'file: "something-else.tar.gz"\n'
            'url: "https://github.com/example/tool/releases/download/v1.3.0/tool-linux-amd64.zip"\n',
        )
        errors = validate(path)
        self.assertTrue(errors)
        self.assertIn("file", errors[0])

    def test_contradictory_architecture_is_rejected(self):
        path = self.write_record(
            "pkg/pkginfo_amd64/tool/_tool@1.3.0",
            f'sha256: "{"b" * 64}"\n'
            'url: "https://github.com/example/tool/releases/download/v1.3.0/tool-linux-arm64.zip"\n',
        )
        self.assertTrue(validate(path))


if __name__ == "__main__":
    unittest.main()
