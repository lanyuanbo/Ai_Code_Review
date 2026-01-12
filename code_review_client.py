#!/usr/bin/env python3
"""Simple Python client to review differences between two git branches with a custom prompt."""

from __future__ import annotations

import argparse
import subprocess
import textwrap
from pathlib import Path
from typing import List, Tuple

DIFF_DISPLAY_LIMIT = 8000  # characters kept from the diff to keep console output concise
MAX_PROMPT_FILE_SIZE = 1024 * 1024  # 1 MB limit for prompt files
GIT_TIMEOUT = 30  # seconds before git commands time out

REPO_ROOT = Path(__file__).resolve().parent


def _run_git(args: List[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, timeout=GIT_TIMEOUT)


def validate_ref_name(ref: str) -> str:
    if not ref or ref.startswith("-") or any(ch.isspace() for ch in ref):
        raise SystemExit(f"无效的分支名称 / Invalid branch name: {ref!r}")
    return ref


def safe_output_path(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if path.is_dir():
        raise SystemExit(f"输出路径指向目录 / Output path is a directory: {path}")
    if not path.parent.exists():
        raise SystemExit(f"输出目录不存在 / Output directory does not exist: {path.parent}")
    return path


def list_branches() -> List[str]:
    try:
        output = _run_git(["branch", "--format", "%(refname:short)"])
    except subprocess.CalledProcessError:
        return []

    branches: List[str] = []
    seen = set()
    for line in output.splitlines():
        cleaned = line.replace("*", "").strip()
        if cleaned and cleaned not in seen:
            branches.append(cleaned)
            seen.add(cleaned)
    return branches


def select_branch(branches: List[str], label: str) -> str:
    print(f"\n选择{label}分支 / Select {label} branch:")
    for idx, name in enumerate(branches, 1):
        print(f" [{idx}] {name}")

    while True:
        value = input(f"请输入 {label} 序号 (1-{len(branches)}) / Enter number: ").strip()
        try:
            choice = int(value)
        except ValueError:
            print("请输入有效序号 / Enter a valid number.")
            continue
        if 1 <= choice <= len(branches):
            return branches[choice - 1]
        print("序号超出范围，请重试 / Choice out of range, try again.")


def read_prompt() -> str:
    print("\n输入自定义提示词（空行结束）/ Enter custom prompt (blank line to finish):")
    lines: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def diff_between_branches(source: str, target: str) -> Tuple[str, str]:
    """Return (stat, diff) for changes present in target relative to source (git diff source..target)."""
    stat = _run_git(["diff", f"{source}..{target}", "--stat"])
    diff = _run_git(["diff", f"{source}..{target}", "--unified=3"])
    return stat.strip(), diff.strip()


def build_review(
    prompt: str, source: str, target: str, stat: str, diff: str, diff_limit: int = DIFF_DISPLAY_LIMIT
) -> str:
    if not stat and not diff:
        return f"分支 {source} 与 {target} 之间没有差异 / No differences between {source} and {target}."

    limited_diff = diff
    if len(diff) > diff_limit:
        limited_diff = diff[:diff_limit] + "\n... 剩余 diff 已截断以保持输出简洁 / diff truncated for brevity ..."

    return textwrap.dedent(
        f"""
        === 按提示词进行 Code Review ===
        自定义提示词 / Custom prompt:
        {prompt or "(未提供提示词) / (No prompt provided)"}

        对比分支 / Comparing: {source} -> {target}

        变更摘要 / Summary:
        {stat or "无文件变化 / No file changes"}

        Review 提示 / Guidance:
        - 根据自定义提示词重点关注潜在风险与需求要点 / Focus on the concerns from the prompt
        - 如需进一步分析，请查看下面的详细 diff / See detailed diff below for more context

        详细 Diff / Detailed Diff:
        {limited_diff or "无 diff 内容 / No diff content"}
        """
    ).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于提示词的分支差异 Code Review 工具")
    parser.add_argument("--from", dest="source", help="起始分支名称")
    parser.add_argument("--to", dest="target", help="目标分支名称")
    parser.add_argument("--prompt", dest="prompt_text", help="直接传入的提示词")
    parser.add_argument("--prompt-file", dest="prompt_file", help="包含提示词的文件路径")
    parser.add_argument("--output", dest="output", help="将 review 结果写入指定文件")
    parser.add_argument(
        "--diff-limit",
        dest="diff_limit",
        type=int,
        default=DIFF_DISPLAY_LIMIT,
        help="截断 diff 的最大字符数 / Maximum characters to keep from diff output",
    )
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_text:
        return args.prompt_text.strip()
    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.is_file():
            raise SystemExit(f"提示词文件不存在 / Prompt file not found: {path}")
        if path.stat().st_size > MAX_PROMPT_FILE_SIZE:
            raise SystemExit(
                f"提示词文件过大（>{MAX_PROMPT_FILE_SIZE} 字节）/ Prompt file too large (> {MAX_PROMPT_FILE_SIZE} bytes): {path}"
            )
        return path.read_text(encoding="utf-8").strip()
    return ""


def main() -> None:
    args = parse_args()
    branches = list_branches()
    if not branches:
        raise SystemExit("未检测到 git 分支，请确认当前目录是有效的 git 仓库 / No git branches detected; confirm the current directory is a valid repository.")

    source = validate_ref_name(args.source or select_branch(branches, "起始/Source"))
    target = validate_ref_name(args.target or select_branch(branches, "目标/Target"))
    if source == target:
        raise SystemExit("起始分支与目标分支相同，无需比较 / Source and target branches are identical.")

    prompt = load_prompt(args) or read_prompt()
    if not prompt:
        print("未提供提示词，将使用空提示继续 / No prompt provided, continuing with an empty prompt.")

    try:
        stat, diff = diff_between_branches(source, target)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"获取 diff 失败 / Failed to retrieve diff: {exc}") from exc

    review = build_review(prompt, source, target, stat, diff, args.diff_limit)
    print("\n" + "=" * 60 + "\n")
    print(review)
    print("\n" + "=" * 60)

    if args.output:
        safe_output_path(args.output).write_text(review, encoding="utf-8")
        print(f"\nReview 结果已写入: {args.output}")


if __name__ == "__main__":
    main()
