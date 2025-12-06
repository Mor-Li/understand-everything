"""
s3_explain_files.py
使用 Gemini API 对代码文件进行通俗易懂的解释（异步版本）
"""

import argparse
import asyncio
import os
from collections import defaultdict
from pathlib import Path

import git
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm as async_tqdm

from utils import get_output_path


# Prompt 模板
EXPLAIN_PROMPT = """这个我完全看不懂讲的啥 你觉得能不能列一个list 列一个task的todo 逐渐的给我一步一步讲讲文中的观点。请说中文

文件路径: {file_path}

文件内容:
```
{file_content}
```"""


async def ask_gemini_async(
    file_path: str,
    file_content: str,
    client: AsyncOpenAI,
    model: str = "gemini-3-pro-preview"
) -> str:
    """
    异步调用 Gemini API 解释文件内容

    Args:
        file_path: 文件路径
        file_content: 文件内容
        client: AsyncOpenAI 客户端
        model: 使用的模型

    Returns:
        解释文本（Markdown 格式）
    """
    prompt = EXPLAIN_PROMPT.format(file_path=file_path, file_content=file_content)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=32000,
            temperature=0.7,
        )

        # 调试信息
        finish_reason = response.choices[0].finish_reason
        content = response.choices[0].message.content or ""

        if finish_reason == "length":
            content += "\n\n_（注：响应因长度限制被截断）_"

        return content.strip()
    except Exception as e:
        return f"# 解释失败\n\n错误信息: {str(e)}"


def get_top_files(repo_path: str, subdir: str, top_n: int | None = None) -> list[tuple[str, int]]:
    """
    获取指定子目录下修改次数最多的文件（按修改次数排序）

    Args:
        repo_path: 仓库路径
        subdir: 子目录（相对于仓库根目录，空字符串或"."表示整个仓库）
        top_n: 返回前 N 个文件，None 表示返回全部

    Returns:
        [(相对文件路径, 修改次数), ...] 列表（已按修改次数降序排序）
    """
    repo = git.Repo(repo_path)
    file_change_count = defaultdict(int)

    # 处理 subdir 参数
    if not subdir or subdir == ".":
        print("📊 分析整个仓库的文件修改历史...")
        filter_prefix = None
    else:
        print(f"📊 分析 {subdir}/ 下的文件修改历史...")
        filter_prefix = subdir + "/"

    for commit in repo.iter_commits():
        try:
            if commit.parents:
                diffs = commit.parents[0].diff(commit)
                for diff in diffs:
                    file_path = diff.a_path or diff.b_path
                    if file_path:
                        # 如果指定了 subdir，只统计该目录下的文件
                        if filter_prefix is None or file_path.startswith(filter_prefix):
                            file_change_count[file_path] += 1
        except Exception:
            continue

    # 只保留当前存在的文件
    repo_root = Path(repo_path)
    existing_files = []
    for file_path, count in file_change_count.items():
        full_path = repo_root / file_path
        if full_path.is_file():
            existing_files.append((file_path, count))

    # 按修改次数排序
    existing_files.sort(key=lambda x: x[1], reverse=True)

    print(f"✓ 找到 {len(existing_files)} 个文件")

    # 返回指定数量
    if top_n is not None:
        return existing_files[:top_n]
    else:
        return existing_files


async def explain_file_async(
    repo_path: str,
    file_rel_path: str,
    output_base: str,
    client: AsyncOpenAI,
    force: bool = False,
    model: str = "gemini-2.5-pro",
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[str, bool]:
    """
    异步解释单个文件并保存为 Markdown

    Args:
        repo_path: 仓库路径
        file_rel_path: 文件相对路径（相对于仓库根目录）
        output_base: 输出基础目录
        client: AsyncOpenAI 客户端
        force: 是否强制重新生成
        model: 使用的模型
        semaphore: 信号量，用于控制并发数

    Returns:
        (文件路径, 是否成功)
    """
    # 使用信号量控制并发
    if semaphore:
        async with semaphore:
            return await _explain_file_impl(
                repo_path, file_rel_path, output_base, client, force, model
            )
    else:
        return await _explain_file_impl(
            repo_path, file_rel_path, output_base, client, force, model
        )


async def _explain_file_impl(
    repo_path: str,
    file_rel_path: str,
    output_base: str,
    client: AsyncOpenAI,
    force: bool,
    model: str,
) -> tuple[str, bool]:
    """
    实际的文件解释实现
    """
    # 构建输入输出路径
    repo_root = Path(repo_path)
    input_file = repo_root / file_rel_path
    output_file = Path(output_base) / (file_rel_path + ".md")

    # 检查是否已存在
    if output_file.exists() and not force:
        return (file_rel_path, True)  # 跳过，视为成功

    # 读取文件内容
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取失败 {file_rel_path}: {e}")
        return (file_rel_path, False)

    # 调用 Gemini（异步）
    try:
        explanation = await ask_gemini_async(file_rel_path, content, client, model)
    except Exception as e:
        print(f"❌ API 调用失败 {file_rel_path}: {e}")
        return (file_rel_path, False)

    # 保存结果
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# {file_rel_path}\n\n")
            f.write(explanation)
        return (file_rel_path, True)
    except Exception as e:
        print(f"❌ 保存失败 {file_rel_path}: {e}")
        return (file_rel_path, False)


async def process_files_batch(
    repo_path: str,
    files: list[tuple[str, int]],
    output_base: str,
    force: bool,
    model: str,
    max_workers: int = 16,
):
    """
    批量异步处理文件

    Args:
        repo_path: 仓库路径
        files: 文件列表 [(文件路径, 修改次数), ...]
        output_base: 输出基础目录
        force: 是否强制重新生成
        model: 使用的模型
        max_workers: 最大并发数（默认 16）
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError("需要设置环境变量 OPENAI_API_KEY")

    # 创建异步客户端
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # 创建信号量控制并发数
    semaphore = asyncio.Semaphore(max_workers)

    # 创建所有任务
    tasks = [
        explain_file_async(
            repo_path, file_path, output_base, client, force, model, semaphore
        )
        for file_path, _ in files
    ]

    # 使用 tqdm 异步进度条
    print(f"\n⚡ 使用 {max_workers} 个并发 worker 处理 {len(tasks)} 个文件")
    print()

    results = []
    for coro in async_tqdm.as_completed(tasks, desc="解释文件", unit="file"):
        result = await coro
        results.append(result)

    # 统计结果
    success_count = sum(1 for _, success in results if success)
    return success_count, len(results)


async def main_async():
    """异步主函数"""
    parser = argparse.ArgumentParser(description="解释代码文件（异步版本）")
    parser.add_argument("repo_path", help="Git 仓库路径")
    parser.add_argument("--subdir", default="", help="要分析的子目录（默认为空，分析整个仓库）")
    parser.add_argument("--top", type=int, help="解释 top N 个文件（与 --percent 互斥）")
    parser.add_argument("--percent", type=int, help="解释前 N%% 的文件（按修改次数排序，与 --top 互斥）")
    parser.add_argument("--output", "-o", help="输出目录（默认：output/<repo_name>/explain-<date>）")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    parser.add_argument("--model", "-m", default="gemini-3-pro-preview", help="使用的模型")
    parser.add_argument("--workers", "-w", type=int, default=16, help="最大并发数（默认：16）")

    args = parser.parse_args()

    # 默认输出路径：output/<repo_name>/explain-<date>
    if args.output is None:
        # 使用仓库名作为 subdir 参数传给 get_output_path
        repo_name = Path(args.repo_path).name
        args.output = get_output_path(args.repo_path, repo_name, "explain")

    # 检查参数
    if args.top is None and args.percent is None:
        args.top = 5  # 默认 top 5
    elif args.top is not None and args.percent is not None:
        print("❌ --top 和 --percent 不能同时使用")
        return

    # 获取所有文件（按修改次数排序）
    all_files = get_top_files(args.repo_path, args.subdir, top_n=None)

    if not all_files:
        print("❌ 没有找到文件")
        return

    # 根据参数选择文件
    if args.percent is not None:
        n_files = max(1, int(len(all_files) * args.percent / 100))
        selected_files = all_files[:n_files]
        if args.subdir:
            print(f"🚀 开始解释 {args.repo_path}/{args.subdir}/ 下前 {args.percent}% 的文件 ({n_files}/{len(all_files)} 个)")
        else:
            print(f"🚀 开始解释 {args.repo_path} 下前 {args.percent}% 的文件 ({n_files}/{len(all_files)} 个)")
    else:
        selected_files = all_files[:args.top]
        if args.subdir:
            print(f"🚀 开始解释 {args.repo_path}/{args.subdir}/ 下的 top {args.top} 文件")
        else:
            print(f"🚀 开始解释 {args.repo_path} 下的 top {args.top} 文件")

    # 显示选中的文件
    print()
    for i, (file_path, count) in enumerate(selected_files, 1):
        print(f"   {i}. {file_path} ({count} 次修改)")

    # 异步批量处理
    success_count, total_count = await process_files_batch(
        args.repo_path,
        selected_files,
        args.output,
        args.force,
        args.model,
        args.workers,
    )

    print(f"\n🎉 完成！成功解释 {success_count}/{total_count} 个文件")


def main():
    """同步入口，运行异步主函数"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
