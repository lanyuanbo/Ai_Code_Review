#!/usr/bin/env python3
"""Simple Python client to review differences between two git branches with a custom prompt."""

from __future__ import annotations

import argparse
import subprocess
import textwrap
from pathlib import Path
from typing import List

DIFF_DISPLAY_LIMIT = 8000

REPO_ROOT = Path(__file__).resolve().parent


def _run_git(args: List[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True)


def list_branches() -> List[str]:
    try:
        output = _run_git(["branch", "--format", "%(refname:short)"])
    except subprocess.CalledProcessError:
        return []

    branches: List[str] = []
    for line in output.splitlines():
        cleaned = line.replace("*", "").strip()
        if cleaned and cleaned not in branches:
            branches.append(cleaned)
    return branches


def select_branch(branches: List[str], label: str) -> str:
    print(f"\n选择{label}分支：")
    for idx, name in enumerate(branches, 1):
        print(f" [{idx}] {name}")

    while True:
        value = input(f"请输入 {label} 序号 (1-{len(branches)}): ").strip()
        if not value.isdigit():
            print("请输入有效序号。")
            continue
        choice = int(value)
        if 1 <= choice <= len(branches):
            return branches[choice - 1]
        print("序号超出范围，请重试。")


def read_prompt() -> str:
    print("\n输入自定义提示词（空行结束）：")
    lines: List[str] = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def diff_between_branches(source: str, target: str) -> tuple[str, str]:
    """Return (stat, diff) for changes needed to go from source to target (git diff source..target)."""
    stat = _run_git(["diff", f"{source}..{target}", "--stat"])
    diff = _run_git(["diff", f"{source}..{target}", "--unified=3"])
    return stat.strip(), diff.strip()


def build_review(prompt: str, source: str, target: str, stat: str, diff: str) -> str:
    if not stat and not diff:
        return f"分支 {source} 与 {target} 之间没有差异。"

    limited_diff = diff
    if len(diff) > DIFF_DISPLAY_LIMIT:
        limited_diff = diff[:DIFF_DISPLAY_LIMIT] + "\n... 剩余 diff 已截断以保持输出简洁 ..."

    return textwrap.dedent(
        f"""
        === 按提示词进行 Code Review ===
        自定义提示词:
        {prompt or "(未提供提示词)"}

        对比分支: {source} -> {target}

        变更摘要:
        {stat or "无文件变化"}

        Review 提示:
        - 根据自定义提示词重点关注潜在风险与需求要点
        - 如需进一步分析，请查看下面的详细 diff

        详细 Diff:
        {limited_diff or "无 diff 内容"}
        """
    ).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于提示词的分支差异 Code Review 工具")
    parser.add_argument("--from", dest="source", help="起始分支名称")
    parser.add_argument("--to", dest="target", help="目标分支名称")
    parser.add_argument("--prompt", dest="prompt_text", help="直接传入的提示词")
    parser.add_argument("--prompt-file", dest="prompt_file", help="包含提示词的文件路径")
    parser.add_argument("--output", dest="output", help="将 review 结果写入指定文件")
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_text:
        return args.prompt_text.strip()
    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.is_file():
            raise SystemExit(f"提示词文件不存在: {path}")
        return path.read_text(encoding="utf-8").strip()
    return ""


def main() -> None:
    args = parse_args()
    branches = list_branches()
    if not branches:
        raise SystemExit("未检测到 git 分支，请确认当前目录是有效的 git 仓库。")

    source = args.source or select_branch(branches, "起始")
    target = args.target or select_branch(branches, "目标")
    if source == target:
        raise SystemExit("起始分支与目标分支相同，无需比较。")

    preset_prompt = load_prompt(args)
    if preset_prompt:
        prompt = preset_prompt
    else:
        prompt = read_prompt()
    if not prompt:
        print("未提供提示词，将使用空提示继续。")

    try:
        stat, diff = diff_between_branches(source, target)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"获取 diff 失败: {exc}") from exc

    review = build_review(prompt, source, target, stat, diff)
    print("\n" + "=" * 60 + "\n")
    print(review)
    print("\n" + "=" * 60)

    if args.output:
        Path(args.output).write_text(review, encoding="utf-8")
        print(f"\nReview 结果已写入: {args.output}")


if __name__ == "__main__":
    main()
