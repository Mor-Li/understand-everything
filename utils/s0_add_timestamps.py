"""
s0_add_timestamps.py
给现有的 output 目录添加 git commit 时间戳
"""

import argparse
from datetime import datetime
from pathlib import Path

import git


def get_commit_date(repo_path: str) -> str | None:
    """
    获取仓库最新 commit 的日期

    Args:
        repo_path: 仓库路径

    Returns:
        日期字符串 (YYYY-MM-DD 格式)
    """
    try:
        repo = git.Repo(repo_path)
        latest_commit = repo.head.commit
        commit_date = datetime.fromtimestamp(latest_commit.committed_date)
        return commit_date.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"❌ 无法获取 {repo_path} 的 commit 日期: {e}")
        return None


def rename_output_dir(output_base: Path, repo_name: str, commit_date: str, dry_run: bool = False):
    """
    重命名 output 目录，添加时间戳

    Args:
        output_base: output 基础目录
        repo_name: 仓库名称
        commit_date: commit 日期 (YYYY-MM-DD)
        dry_run: 是否只打印而不执行
    """
    old_dir = output_base / repo_name

    if not old_dir.exists():
        print(f"⏭️  跳过 {old_dir}（目录不存在）")
        return

    # 检查是否需要重命名
    subdirs = list(old_dir.iterdir())
    needs_rename = False

    for subdir in subdirs:
        if subdir.is_dir() and not subdir.name.startswith("explain-"):
            # 如果有 explain 目录（没有时间戳），需要重命名
            if subdir.name == "explain":
                needs_rename = True
                break

    if not needs_rename:
        print(f"⏭️  跳过 {old_dir}（已经有时间戳）")
        return

    # 重命名 explain 目录
    explain_dir = old_dir / "explain"
    if explain_dir.exists():
        new_explain_dir = old_dir / f"explain-{commit_date}"

        if new_explain_dir.exists():
            print(f"⚠️  目标目录已存在: {new_explain_dir}")
            return

        if dry_run:
            print(f"🔍 [Dry-run] 将重命名: {explain_dir} -> {new_explain_dir}")
        else:
            explain_dir.rename(new_explain_dir)
            print(f"✓ 已重命名: {explain_dir} -> {new_explain_dir}")

    # 重命名 website 目录（如果存在）
    website_dir = old_dir / "website"
    if website_dir.exists():
        new_website_dir = old_dir / f"website-{commit_date}"

        if new_website_dir.exists():
            print(f"⚠️  目标目录已存在: {new_website_dir}")
            return

        if dry_run:
            print(f"🔍 [Dry-run] 将重命名: {website_dir} -> {new_website_dir}")
        else:
            website_dir.rename(new_website_dir)
            print(f"✓ 已重命名: {website_dir} -> {new_website_dir}")


def main():
    parser = argparse.ArgumentParser(description="给 output 目录添加 git commit 时间戳")
    parser.add_argument("--output-base", default="output", help="output 基础目录")
    parser.add_argument("--dry-run", action="store_true", help="只打印不执行")

    args = parser.parse_args()

    output_base = Path(args.output_base)

    if not output_base.exists():
        print(f"❌ output 目录不存在: {output_base}")
        return

    # 处理每个仓库
    repos = {
        "Megatron-LM": "repo/Megatron-LM",
        "verl": "repo/verl",
    }

    print("🚀 开始处理 output 目录...\n")

    for repo_name, repo_path in repos.items():
        print(f"📦 处理 {repo_name}...")

        # 获取 commit 日期
        commit_date = get_commit_date(repo_path)
        if commit_date is None:
            print(f"⏭️  跳过 {repo_name}\n")
            continue

        print(f"   Commit 日期: {commit_date}")

        # 重命名目录
        rename_output_dir(output_base, repo_name, commit_date, args.dry_run)
        print()

    if args.dry_run:
        print("🔍 Dry-run 模式完成！使用不带 --dry-run 参数执行以实际重命名")
    else:
        print("🎉 完成！")


if __name__ == "__main__":
    main()
