"""
s2_analyze_stats.py
分析指定子目录下文件的 git 修改统计信息
"""

import argparse
from collections import defaultdict
from pathlib import Path

import git
import numpy as np
import tiktoken


# 初始化 tokenizer（使用 o200k_base，对应 GPT-5/Gemini 等新模型）
tokenizer = tiktoken.get_encoding("o200k_base")


def count_tokens(file_path: Path) -> int:
    """
    使用 tiktoken 计算文件的实际 token 数量

    Args:
        file_path: 文件路径

    Returns:
        token 数量
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tokens = tokenizer.encode(content)
            return len(tokens)
    except:
        return 0


def analyze_repo_stats(repo_path: str, subdir: str):
    """
    分析仓库指定子目录的统计信息

    Args:
        repo_path: 仓库路径
        subdir: 子目录（相对于仓库根目录）
    """
    repo = git.Repo(repo_path)
    repo_root = Path(repo_path)
    file_change_count = defaultdict(int)

    print(f"📊 正在分析 {subdir}/ 的 git 历史...")
    print()

    # 统计每个文件的修改次数
    for commit in repo.iter_commits():
        try:
            if commit.parents:
                diffs = commit.parents[0].diff(commit)
                for diff in diffs:
                    file_path = diff.a_path or diff.b_path
                    if file_path and file_path.startswith(subdir + "/"):
                        file_change_count[file_path] += 1
        except Exception:
            continue

    # 只保留当前存在的文件
    existing_files = []
    total_tokens = 0

    print("🔢 正在计算 token 数量（使用 tiktoken o200k_base）...")
    for file_path, count in file_change_count.items():
        full_path = repo_root / file_path
        if full_path.is_file():
            tokens = count_tokens(full_path)
            existing_files.append((file_path, count, tokens))
            total_tokens += tokens

    if not existing_files:
        print("❌ 没有找到文件")
        return

    # 按修改次数排序
    existing_files.sort(key=lambda x: x[1], reverse=True)

    # 提取修改次数列表
    change_counts = [count for _, count, _ in existing_files]

    # 计算分位数
    percentiles = [50, 75, 90, 95, 99]
    percentile_values = np.percentile(change_counts, percentiles)

    # ========== 打印统计信息 ==========

    print("=" * 70)
    print(f"📁 子目录: {subdir}/")
    print("=" * 70)
    print()

    print(f"📈 总体统计:")
    print(f"   - 总文件数: {len(existing_files)}")
    print(f"   - 总 Token 数: {total_tokens:,} (~{total_tokens/1000:.1f}K tokens)")
    print(f"   - 平均每文件: {total_tokens/len(existing_files):.0f} tokens")
    print()

    print(f"🔢 修改次数分布:")
    print(f"   - 最小值: {min(change_counts)}")
    print(f"   - 最大值: {max(change_counts)}")
    print(f"   - 平均值: {np.mean(change_counts):.1f}")
    print(f"   - 中位数: {np.median(change_counts):.1f}")
    print()

    print(f"📊 修改次数分位数:")
    for p, v in zip(percentiles, percentile_values):
        print(f"   - P{p:2d}: {v:.0f} 次")
    print()

    # 按百分位展示文件数量和 token 统计
    print("=" * 70)
    print("📦 按修改频率分层统计 (从高到低)")
    print("=" * 70)
    print()

    percentages = [1, 5, 10, 20, 30, 50, 80, 90, 100]

    for pct in percentages:
        n_files = int(len(existing_files) * pct / 100)
        if n_files == 0:
            n_files = 1

        top_files = existing_files[:n_files]
        top_tokens = sum(tokens for _, _, tokens in top_files)
        min_changes = min(count for _, count, _ in top_files) if top_files else 0
        max_changes = max(count for _, count, _ in top_files) if top_files else 0

        print(f"前 {pct:3d}% 文件 (Top {n_files:4d}):")
        print(f"   - 修改次数范围: {min_changes:3d} ~ {max_changes:3d}")
        print(f"   - Token 总量: {top_tokens:,} (~{top_tokens/1000:.1f}K tokens)")
        print(f"   - 平均每文件: {top_tokens/n_files:.0f} tokens")
        print()

    # 展示 Top 10 文件
    print("=" * 70)
    print("🏆 Top 10 修改最频繁的文件")
    print("=" * 70)
    print()

    for i, (file_path, count, tokens) in enumerate(existing_files[:10], 1):
        # 简化路径显示
        display_path = file_path
        if len(display_path) > 55:
            display_path = "..." + display_path[-52:]

        print(f"{i:2d}. {display_path}")
        print(f"    修改次数: {count:3d}  |  Token 数: {tokens:,} (~{tokens/1000:.1f}K)")
        print()


def main():
    parser = argparse.ArgumentParser(description="分析仓库子目录的统计信息")
    parser.add_argument("repo_path", help="Git 仓库路径")
    parser.add_argument("--subdir", default="mshrl", help="要分析的子目录")

    args = parser.parse_args()

    analyze_repo_stats(args.repo_path, args.subdir)


if __name__ == "__main__":
    main()
