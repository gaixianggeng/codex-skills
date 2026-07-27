#!/usr/bin/env python3
"""WorkBuddy 公开市场 Skill 的只读检索与按需安装器。"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CATALOG_PATH = SKILL_DIR / "references" / "catalog.json"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class NavigatorError(RuntimeError):
    """面向用户的可预期错误。"""


def load_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        catalog = json.load(file)
    if catalog.get("schema_version") != 1:
        raise NavigatorError("不支持的目录版本。")
    return catalog


def default_destination() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "skills"
    return Path.home() / ".codex" / "skills"


def resolve_destination(raw: str | None) -> Path:
    destination = Path(raw).expanduser() if raw else default_destination()
    destination = destination.resolve()
    if destination in {Path("/"), Path.home().resolve()}:
        raise NavigatorError(f"拒绝使用过宽的安装目录：{destination}")
    return destination


def normalize_category(
    value: str, categories: list[dict[str, Any]]
) -> str:
    normalized = value.strip().casefold()
    for item in categories:
        if normalized in {
            str(item["id"]).casefold(),
            str(item["label"]).casefold(),
        }:
            return str(item["id"])
    valid = "、".join(str(item["id"]) for item in categories)
    raise NavigatorError(f"未知分类：{value}。可用分类：{valid}")


def find_skill(value: str, skills: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = value.strip().casefold()
    by_id = [item for item in skills if str(item["id"]).casefold() == normalized]
    if by_id:
        return by_id[0]
    by_name = [
        item for item in skills if str(item.get("name", "")).casefold() == normalized
    ]
    if len(by_name) == 1:
        return by_name[0]
    if len(by_name) > 1:
        matches = "、".join(str(item["id"]) for item in by_name)
        raise NavigatorError(f"名称 {value} 对应多个目录，请改用目录 ID：{matches}")
    raise NavigatorError(f"目录中没有找到 Skill：{value}")


def select_skills(
    args: argparse.Namespace, catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    skills = list(catalog["skills"])
    if args.all:
        return sorted(skills, key=lambda item: str(item["id"]))

    selected: dict[str, dict[str, Any]] = {}
    category_ids = {
        normalize_category(value, catalog["categories"])
        for value in (args.category or [])
    }
    for item in skills:
        if item["category"] in category_ids:
            selected[str(item["id"])] = item
    for value in args.skill or []:
        item = find_skill(value, skills)
        selected[str(item["id"])] = item
    return [selected[key] for key in sorted(selected)]


def needs_configuration(item: dict[str, Any]) -> bool:
    value = str(item.get("prerequisites", "")).strip()
    return bool(value and value not in {"无", "无（可选 API/账号以增强能力）"})


def installed_state(
    selected: list[dict[str, Any]], destination: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    existing: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for item in selected:
        target = destination / str(item["id"])
        (existing if target.exists() else pending).append(item)
    return existing, pending


def plan_payload(
    selected: list[dict[str, Any]],
    destination: Path,
    source: dict[str, Any],
) -> dict[str, Any]:
    existing, pending = installed_state(selected, destination)
    return {
        "selected_count": len(selected),
        "pending_count": len(pending),
        "existing_count": len(existing),
        "requires_configuration_count": sum(
            1 for item in selected if needs_configuration(item)
        ),
        "destination": str(destination),
        "source_repository": source["repository"],
        "source_commit": source["commit"],
        "selected": [item["id"] for item in selected],
        "existing": [item["id"] for item in existing],
    }


def print_categories(catalog: dict[str, Any], as_json: bool) -> None:
    categories = catalog["categories"]
    if as_json:
        print(json.dumps(categories, ensure_ascii=False, indent=2))
        return
    print(f"WorkBuddy Skill 分类（共 {len(catalog['skills'])} 个）")
    for item in categories:
        print(f"- {item['id']}: {item['label']}（{item['count']}）")


def filtered_listing(
    args: argparse.Namespace, catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    skills = list(catalog["skills"])
    if args.category:
        category_ids = {
            normalize_category(value, catalog["categories"])
            for value in args.category
        }
        skills = [item for item in skills if item["category"] in category_ids]
    if args.search:
        query = args.search.casefold()
        skills = [
            item
            for item in skills
            if query
            in " ".join(
                [
                    str(item.get("id", "")),
                    str(item.get("name", "")),
                    str(item.get("description", "")),
                    str(item.get("category_label", "")),
                ]
            ).casefold()
        ]
    return sorted(skills, key=lambda item: (str(item["category"]), str(item["id"])))


def print_listing(items: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        print("没有匹配的 Skill。")
        return
    for item in items:
        print(
            f"- {item['id']} | {item['category_label']} | "
            f"{item['description']} | 前置：{item['prerequisites']}"
        )
    print(f"共 {len(items)} 个。")


def print_plan(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print("安装计划")
    print(f"- 已选择：{payload['selected_count']}")
    print(f"- 待安装：{payload['pending_count']}")
    print(f"- 已存在：{payload['existing_count']}")
    print(f"- 可能需要额外配置：{payload['requires_configuration_count']}")
    print(f"- 目标目录：{payload['destination']}")
    print(
        f"- 来源：{payload['source_repository']}@"
        f"{payload['source_commit']}"
    )
    if payload["existing"]:
        print(f"- 已存在目录：{', '.join(payload['existing'])}")


def run_git(args: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> None:
    result = subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise NavigatorError(f"Git 操作失败：{detail}")


def validate_source_directory(source_dir: Path) -> None:
    if not source_dir.is_dir():
        raise NavigatorError(f"上游目录不存在：{source_dir.name}")
    skill_md = source_dir / "SKILL.md"
    if not skill_md.is_file() or skill_md.is_symlink():
        raise NavigatorError(f"{source_dir.name} 缺少安全的 SKILL.md")
    for path in source_dir.rglob("*"):
        if path.is_symlink():
            raise NavigatorError(f"{source_dir.name} 包含符号链接，已拒绝安装：{path.name}")


def install_selected(
    selected: list[dict[str, Any]],
    destination: Path,
    source: dict[str, Any],
    skip_existing: bool,
) -> dict[str, Any]:
    if shutil.which("git") is None:
        raise NavigatorError("未找到 git，无法下载上游 Skill。")

    existing, pending = installed_state(selected, destination)
    if existing and not skip_existing:
        names = "、".join(str(item["id"]) for item in existing)
        raise NavigatorError(
            f"以下目标目录已经存在，未做覆盖：{names}。"
            "如确认跳过这些目录，请使用 --skip-existing。"
        )
    if not pending:
        return {"installed": [], "skipped": [item["id"] for item in existing]}

    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="workbuddy-skills-") as temp_raw:
        temp_dir = Path(temp_raw)
        checkout = temp_dir / "source"
        checkout.mkdir()

        run_git(["git", "init", "--quiet"], cwd=checkout)
        run_git(
            ["git", "remote", "add", "origin", f"https://github.com/{source['repository']}.git"],
            cwd=checkout,
        )
        run_git(["git", "sparse-checkout", "init", "--no-cone"], cwd=checkout)
        sparse_paths = "\n".join(str(item["source_path"]) for item in pending) + "\n"
        run_git(
            ["git", "sparse-checkout", "set", "--no-cone", "--stdin"],
            cwd=checkout,
            input_text=sparse_paths,
        )
        run_git(
            [
                "git",
                "fetch",
                "--quiet",
                "--depth",
                "1",
                "--filter=blob:none",
                "origin",
                str(source["commit"]),
            ],
            cwd=checkout,
        )
        run_git(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=checkout)

        stage = Path(tempfile.mkdtemp(prefix=".workbuddy-stage-", dir=destination))
        try:
            for item in pending:
                skill_id = str(item["id"])
                if not SAFE_ID_RE.fullmatch(skill_id):
                    raise NavigatorError(f"非法 Skill ID：{skill_id}")
                source_dir = checkout / str(item["source_path"])
                validate_source_directory(source_dir)
                shutil.copytree(source_dir, stage / skill_id)

            installed: list[str] = []
            for item in pending:
                skill_id = str(item["id"])
                target = destination / skill_id
                if target.exists():
                    raise NavigatorError(f"安装期间目标目录出现冲突：{target}")
                os.replace(stage / skill_id, target)
                installed.append(skill_id)
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    return {
        "installed": installed,
        "skipped": [str(item["id"]) for item in existing],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="浏览并按需安装 WorkBuddy 公开市场 Skill。"
    )
    parser.add_argument("--list-categories", action="store_true", help="列出分类")
    parser.add_argument("--list", action="store_true", help="列出 Skill")
    parser.add_argument("--search", help="按名称、描述或分类搜索")
    parser.add_argument("--category", action="append", help="分类 ID 或中文名称，可重复")
    parser.add_argument("--skill", action="append", help="Skill 目录 ID，可重复")
    parser.add_argument("--all", action="store_true", help="选择全部 295 个 Skill")
    parser.add_argument("--dry-run", action="store_true", help="只展示安装计划")
    parser.add_argument("--yes", action="store_true", help="确认执行写入")
    parser.add_argument(
        "--confirm-all",
        action="store_true",
        help="再次确认全量安装，仅与 --all --yes 一起使用",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="跳过已存在目录，永不覆盖",
    )
    parser.add_argument("--dest", help="自定义安装目录，默认 ~/.codex/skills")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    catalog = load_catalog()

    if args.list_categories:
        print_categories(catalog, args.json)
        return 0

    if args.list or args.search:
        print_listing(filtered_listing(args, catalog), args.json)
        return 0

    selected = select_skills(args, catalog)
    if not selected:
        raise NavigatorError(
            "请使用 --list-categories、--list、--search，"
            "或通过 --skill / --category / --all 选择安装范围。"
        )

    destination = resolve_destination(args.dest)
    payload = plan_payload(selected, destination, catalog["source"])
    if args.dry_run:
        print_plan(payload, args.json)
        return 0

    if not args.yes:
        print_plan(payload, args.json)
        raise NavigatorError("尚未确认写入。请先核对计划，确认后加 --yes。")
    if args.all and not args.confirm_all:
        raise NavigatorError("全量安装需要额外提供 --confirm-all。")

    result = install_selected(
        selected,
        destination,
        catalog["source"],
        args.skip_existing,
    )
    output = {
        **payload,
        "installed_count": len(result["installed"]),
        "skipped_count": len(result["skipped"]),
        "installed": result["installed"],
        "skipped": result["skipped"],
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"安装完成：{output['installed_count']} 个。")
        if output["skipped_count"]:
            print(f"跳过已有目录：{output['skipped_count']} 个。")
        print("新 Skill 从下一轮对话开始可用。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NavigatorError as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(2)
