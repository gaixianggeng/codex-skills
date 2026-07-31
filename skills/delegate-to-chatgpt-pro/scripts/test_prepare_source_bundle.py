#!/usr/bin/env python3
"""prepare_source_bundle.py 的无第三方依赖测试。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("prepare_source_bundle.py")
SPEC = importlib.util.spec_from_file_location("prepare_source_bundle", SCRIPT_PATH)
assert SPEC and SPEC.loader
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PrepareSourceBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.name", "Test User"],
            check=True,
        )
        (self.repo / "src").mkdir()
        (self.repo / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (self.repo / "README.md").write_text("# Test\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "initial"], check=True
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_requires_include_or_all(self) -> None:
        result = run("--repo", str(self.repo))
        self.assertEqual(result.returncode, 2)
        self.assertIn("必须指定至少一个 --include", result.stderr)

    def test_creates_scoped_archive_and_hash(self) -> None:
        output = Path(self.temporary.name) / "bundle.zip"
        result = run(
            "--repo",
            str(self.repo),
            "--include",
            "src",
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["file_count"], 1)
        self.assertEqual(
            summary["sha256"], hashlib.sha256(output.read_bytes()).hexdigest()
        )
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn("repo/src/main.py", names)
            self.assertIn("repo/BUNDLE-MANIFEST.json", names)
            self.assertNotIn("repo/README.md", names)

    def test_all_is_explicit_and_includes_git_visible_files(self) -> None:
        output = Path(self.temporary.name) / "all.zip"
        result = run(
            "--repo",
            str(self.repo),
            "--all",
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["file_count"], 2)
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn("repo/src/main.py", names)
            self.assertIn("repo/README.md", names)

    def test_secret_scan_blocks_archive(self) -> None:
        secret = self.repo / "src" / "secret.txt"
        secret.write_text(
            "token='abcdefghijklmnopqrstuvwxyz123456'\n", encoding="utf-8"
        )
        output = Path(self.temporary.name) / "blocked.zip"
        result = run(
            "--repo",
            str(self.repo),
            "--include",
            "src",
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")
        self.assertFalse(output.exists())

    def test_rejects_path_traversal_and_existing_output(self) -> None:
        traversal = run(
            "--repo",
            str(self.repo),
            "--include",
            "../outside",
        )
        self.assertEqual(traversal.returncode, 2)

        output = Path(self.temporary.name) / "existing.zip"
        output.write_text("preserve", encoding="utf-8")
        existing = run(
            "--repo",
            str(self.repo),
            "--include",
            "src",
            "--output",
            str(output),
        )
        self.assertEqual(existing.returncode, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_exclusive_writer_does_not_overwrite_existing_file(self) -> None:
        staging_parent = Path(self.temporary.name) / "staging-parent"
        staging = staging_parent / "repo"
        staging.mkdir(parents=True)
        (staging / "file.txt").write_text("content", encoding="utf-8")
        output = Path(self.temporary.name) / "reserved.zip"
        output.write_text("preserve", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            BUNDLE.write_archive_exclusive(output, staging)
        self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_content_snapshot_detects_change(self) -> None:
        source = self.repo / "src" / "main.py"
        original_hash = BUNDLE.sha256_file(source)
        files = [
            {
                "path": "src/main.py",
                "bytes": source.stat().st_size,
                "sha256": original_hash,
            }
        ]
        source.write_text("print('changed')\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "文件内容发生变化"):
            BUNDLE.assert_source_snapshot(
                repo=self.repo,
                files=files,
                expected_head=subprocess.check_output(
                    ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                    text=True,
                ).strip(),
                expected_selected_paths=["src/main.py"],
                includes=["src/main.py"],
                excludes=[],
            )


if __name__ == "__main__":
    unittest.main()
