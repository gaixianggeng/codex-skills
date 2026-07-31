#!/usr/bin/env python3
"""从 Git 可见文件创建用于外部工程协作的脱敏源码 ZIP。"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


EXCLUDED_DIRS = {
    ".git",
    ".cache",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    ".venv",
    ".yarn",
    "__pycache__",
    "build",
    "coverage",
    "deriveddata",
    "dist",
    "logs",
    "node_modules",
    "out",
    "pods",
    "target",
    "tmp",
    "vendor",
}

SENSITIVE_BASENAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "auth.json",
    "credentials.json",
    "cookies.json",
    "id_dsa",
    "id_ed25519",
    "id_ecdsa",
    "id_rsa",
    "service-account.json",
}

SENSITIVE_SUFFIXES = {
    ".cer",
    ".crt",
    ".db",
    ".der",
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
}

# 仅使用高置信度格式，降低测试夹具和文档示例造成的误报。
SECRET_PATTERNS = (
    ("private-key", re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")),
    ("openai-api-key", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("github-token", re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("github-fine-grained-token", re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws-access-key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("google-api-key", re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("slack-token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("stripe-live-key", re.compile(rb"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
    (
        "jwt-token",
        re.compile(
            rb"\beyJ[A-Za-z0-9_-]{20,}\."
            rb"[A-Za-z0-9_-]{20,}\."
            rb"[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    (
        "telegram-bot-token",
        re.compile(rb"\b\d{8,10}:[A-Za-z0-9_-]{35,}\b"),
    ),
    ("aliyun-access-key", re.compile(rb"\bLTAI[A-Za-z0-9]{12,20}\b")),
    ("tencent-secret-id", re.compile(rb"\bAKID[A-Za-z0-9]{13,40}\b")),
    (
        "database-credential-uri",
        re.compile(
            rb"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)"
            rb"://[^:\s/@]+:[^@\s/]{4,}@",
            re.IGNORECASE,
        ),
    ),
    (
        "generic-secret-assignment",
        re.compile(
            rb"\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|token|secret)"
            rb"\s*[:=]\s*[\"'][A-Za-z0-9_./+=-]{20,}[\"']",
            re.IGNORECASE,
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="创建脱敏源码 ZIP；仅收集 Git 已跟踪或未忽略的未跟踪文件。"
    )
    parser.add_argument("--repo", required=True, help="Git 仓库绝对路径")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="仅包含相对路径、目录或 glob；可重复",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="显式允许收集全部 Git 可见文件",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="额外排除相对路径、目录或 glob；可重复",
    )
    parser.add_argument("--output", help="输出 ZIP 路径；默认写入系统临时目录")
    parser.add_argument(
        "--max-file-mb",
        type=int,
        default=20,
        help="单文件上限，默认 20 MiB",
    )
    parser.add_argument(
        "--max-total-mb",
        type=int,
        default=100,
        help="未压缩内容总上限，默认 100 MiB",
    )
    return parser.parse_args()


def run_git(repo: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} 失败：{message}")
    return result.stdout


def normalize_rule(rule: str) -> str:
    normalized = rule.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"路径规则必须是仓库内相对路径：{rule}")
    return normalized


def matches_rule(path: str, rule: str) -> bool:
    if any(char in rule for char in "*?["):
        return fnmatch.fnmatch(path, rule) or fnmatch.fnmatch(path, f"{rule}/**")
    return path == rule or path.startswith(f"{rule}/")


def is_default_excluded(path: str) -> str | None:
    pure = PurePosixPath(path)
    lowered_parts = {part.lower() for part in pure.parts[:-1]}
    excluded_dir = lowered_parts.intersection(EXCLUDED_DIRS)
    if excluded_dir:
        return f"excluded-dir:{sorted(excluded_dir)[0]}"

    basename = pure.name.lower()
    if basename == ".env" or basename.startswith(".env."):
        return "sensitive-env"
    if basename in SENSITIVE_BASENAMES:
        return "sensitive-name"
    if pure.suffix.lower() in SENSITIVE_SUFFIXES:
        return "sensitive-suffix"
    if basename.startswith(("cookies.", "credentials.", "service-account.")):
        return "sensitive-name"
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_file(path: Path, relative_path: str) -> list[dict[str, object]]:
    data = path.read_bytes()
    hits: list[dict[str, object]] = []
    for rule_name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(data):
            line = data.count(b"\n", 0, match.start()) + 1
            hits.append({"path": relative_path, "line": line, "rule": rule_name})
    return hits


def safe_repo_name(repo: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", repo.name).strip("-")
    return name or "source"


def choose_output(repo: Path, requested: str | None) -> Path:
    if requested:
        output = Path(requested).expanduser().resolve()
        if output.suffix.lower() != ".zip":
            raise ValueError("--output 必须以 .zip 结尾")
        output.parent.mkdir(parents=True, exist_ok=True)
    else:
        bundle_dir = Path(tempfile.gettempdir()) / "codex-pro-bundles"
        bundle_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = bundle_dir / (
            f"{safe_repo_name(repo)}-{timestamp}-{uuid.uuid4().hex[:8]}.zip"
        )
    if output.exists():
        raise FileExistsError(f"拒绝覆盖已有文件：{output}")
    return output


def select_candidate_paths(
    candidate_paths: list[str],
    includes: list[str],
    excludes: list[str],
) -> tuple[list[str], list[dict[str, str]]]:
    selected: list[str] = []
    skipped: list[dict[str, str]] = []
    for relative_path in candidate_paths:
        if includes and not any(
            matches_rule(relative_path, rule) for rule in includes
        ):
            continue
        if any(matches_rule(relative_path, rule) for rule in excludes):
            skipped.append({"path": relative_path, "reason": "user-exclude"})
            continue
        default_reason = is_default_excluded(relative_path)
        if default_reason:
            skipped.append({"path": relative_path, "reason": default_reason})
            continue
        selected.append(relative_path)
    return selected, skipped


def assert_source_snapshot(
    repo: Path,
    files: list[dict[str, object]],
    expected_head: str,
    expected_selected_paths: list[str],
    includes: list[str],
    excludes: list[str],
) -> None:
    """在压缩前确认入包路径和源文件内容仍与暂存副本一致。"""
    current_head = run_git(repo, "rev-parse", "HEAD", check=False).decode().strip()
    current_head = current_head or "UNBORN"
    if current_head != expected_head:
        raise RuntimeError("打包期间 HEAD 发生变化，请重新生成 bundle")

    raw_paths = run_git(
        repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
    )
    current_candidates = sorted(
        path.decode("utf-8", "surrogateescape")
        for path in raw_paths.split(b"\0")
        if path
    )
    current_selected, _ = select_candidate_paths(
        current_candidates, includes, excludes
    )
    if current_selected != expected_selected_paths:
        raise RuntimeError("打包期间入包路径集合发生变化，请重新生成 bundle")

    for file_info in files:
        relative_path = str(file_info["path"])
        source = repo / relative_path
        try:
            source_stat = source.lstat()
        except FileNotFoundError as error:
            raise RuntimeError(
                f"打包期间文件被删除：{relative_path}"
            ) from error
        if not stat.S_ISREG(source_stat.st_mode) or stat.S_ISLNK(source_stat.st_mode):
            raise RuntimeError(f"打包期间文件类型发生变化：{relative_path}")
        if sha256_file(source) != file_info["sha256"]:
            raise RuntimeError(f"打包期间文件内容发生变化：{relative_path}")


def write_archive_exclusive(output: Path, staging: Path) -> None:
    """以 O_EXCL 原子占用目标路径，避免覆盖或跟随竞争创建的符号链接。"""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(output, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w+b") as output_file:
            descriptor = -1
            with zipfile.ZipFile(
                output_file,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for path in sorted(staging.rglob("*")):
                    if path.is_file():
                        archive.write(
                            path, path.relative_to(staging.parent).as_posix()
                        )
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        output.unlink(missing_ok=True)
        raise


def main() -> int:
    args = parse_args()
    if not args.include and not args.all:
        raise ValueError(
            "必须指定至少一个 --include，或显式使用 --all 收集整个仓库"
        )
    if args.include and args.all:
        raise ValueError("--include 与 --all 不能同时使用")

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"仓库不存在：{repo}")

    git_root = Path(
        run_git(repo, "rev-parse", "--show-toplevel").decode().strip()
    ).resolve()
    if git_root != repo:
        raise ValueError(f"--repo 必须是 Git 根目录：{git_root}")

    includes = [normalize_rule(rule) for rule in args.include]
    excludes = [normalize_rule(rule) for rule in args.exclude]
    max_file_bytes = args.max_file_mb * 1024 * 1024
    max_total_bytes = args.max_total_mb * 1024 * 1024
    if max_file_bytes <= 0 or max_total_bytes <= 0:
        raise ValueError("文件和总大小上限必须大于 0")

    raw_paths = run_git(
        repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
    )
    candidate_paths = sorted(
        path.decode("utf-8", "surrogateescape")
        for path in raw_paths.split(b"\0")
        if path
    )
    selected_paths, initially_skipped = select_candidate_paths(
        candidate_paths, includes, excludes
    )

    head_result = run_git(repo, "rev-parse", "HEAD", check=False)
    head_commit = head_result.decode().strip() or "UNBORN"
    status_before = run_git(
        repo, "status", "--porcelain=v1", "--untracked-files=normal"
    ).decode("utf-8", "replace")

    output = choose_output(repo, args.output)
    skipped: list[dict[str, str]] = list(initially_skipped)
    files: list[dict[str, object]] = []
    scan_hits: list[dict[str, object]] = []
    total_bytes = 0

    with tempfile.TemporaryDirectory(prefix="codex-pro-bundle-") as temporary:
        staging = Path(temporary) / safe_repo_name(repo)
        staging.mkdir()

        for relative_path in selected_paths:
            source = repo / relative_path
            try:
                file_stat = source.lstat()
            except FileNotFoundError:
                skipped.append({"path": relative_path, "reason": "missing"})
                continue
            if stat.S_ISLNK(file_stat.st_mode):
                skipped.append({"path": relative_path, "reason": "symlink"})
                continue
            if not stat.S_ISREG(file_stat.st_mode):
                skipped.append({"path": relative_path, "reason": "not-regular-file"})
                continue
            if file_stat.st_size > max_file_bytes:
                skipped.append({"path": relative_path, "reason": "file-too-large"})
                continue
            if total_bytes + file_stat.st_size > max_total_bytes:
                raise RuntimeError(
                    f"内容超过 {args.max_total_mb} MiB；请用 --include/--exclude 缩小范围"
                )

            destination = staging / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied_size = destination.stat().st_size
            total_bytes += copied_size
            scan_hits.extend(scan_file(destination, relative_path))
            files.append(
                {
                    "path": relative_path,
                    "bytes": copied_size,
                    "sha256": sha256_file(destination),
                }
            )

        if not files:
            raise RuntimeError("没有可打包文件；请检查 --include 和默认排除规则")

        if scan_hits:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "secret-scan-hit",
                        "hits": scan_hits,
                        "message": "排除命中文件或缩小上下文后重新生成；不要绕过扫描。",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 3

        assert_source_snapshot(
            repo=repo,
            files=files,
            expected_head=head_commit,
            expected_selected_paths=selected_paths,
            includes=includes,
            excludes=excludes,
        )

        status_after = run_git(
            repo, "status", "--porcelain=v1", "--untracked-files=normal"
        ).decode("utf-8", "replace")
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repo_name": repo.name,
            "head_commit": head_commit,
            "dirty": bool(status_before.strip()),
            "worktree_changed_during_bundle": status_before != status_after,
            "include_rules": includes or ["<all-git-visible-files>"],
            "exclude_rules": excludes,
            "file_count": len(files),
            "source_bytes": total_bytes,
            "files": files,
            "skipped": skipped,
        }
        manifest_path = staging / "BUNDLE-MANIFEST.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        write_archive_exclusive(output, staging)

    archive_sha256 = sha256_file(output)
    summary = {
        "status": "ok",
        "archive": str(output),
        "archive_bytes": output.stat().st_size,
        "sha256": archive_sha256,
        "head_commit": head_commit,
        "dirty": bool(status_before.strip()),
        "worktree_changed_during_bundle": status_before != status_after,
        "file_count": len(files),
        "source_bytes": total_bytes,
        "skipped_count": len(skipped),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {"status": "error", "message": str(error)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
