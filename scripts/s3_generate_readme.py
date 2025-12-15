"""
s4_generate_readme.py
递归生成各层级目录的 README.md（自底向上，异步版本）
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path

import tiktoken
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm as async_tqdm
import sys

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.utils import get_output_path

# 初始化 tokenizer
tokenizer = tiktoken.get_encoding("o200k_base")

# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)

# 常量
MAX_TOKENS = 200_000  # 200K token 限制

# Prompt 模板
README_PROMPT = """以下是 {folder_path} 目录的结构和**直接内容**：

## 📁 目录结构

{tree_structure}

## 📄 详细内容

{content}

⚠️ **重要提示**：
- 请专注于描述 `{folder_path}` **这一层级**的功能和结构
- 子文件夹（📁标记的）已经有各自的 README，这里只需概括性地提到它们的作用
- **不要重复子文件夹内部的详细内容**（如具体文件名、详细实现）
- 优先描述当前层级的直接文件（📄标记的）

请你用最通俗易懂的语言、用比喻的方式描述一下：
1. 当前这个文件夹（{folder_path}）主要负责什么功能？
2. 这个文件夹下的各个**直接文件**分别是干什么的？
3. 子文件夹的作用是什么？（概括即可，不要展开细节）
4. 给我一个高层的认知，让我能快速理解这部分代码的作用。

请用简洁、通俗、易懂的语气回答，说中文。"""


def count_tokens(text: str) -> int:
    """计算文本的 token 数量"""
    return len(tokenizer.encode(text, disallowed_special=()))


def truncate_content(contents: list[tuple[str, str, int]], target_tokens: int) -> list[tuple[str, str]]:
    """
    等比例截断内容以满足 token 限制

    Args:
        contents: [(name, content, token_count), ...]
        target_tokens: 目标 token 数量

    Returns:
        [(name, truncated_content), ...]
    """
    total_tokens = sum(tc for _, _, tc in contents)
    ratio = target_tokens / total_tokens

    logger.warning(f"⚠️  内容超出 {MAX_TOKENS:,} tokens 限制")
    logger.warning(f"   总量: {total_tokens:,} tokens")
    logger.warning(f"   压缩比例: {ratio:.2%}")

    truncated = []
    for name, content, token_count in contents:
        # 计算该文件应保留的 token 数量
        keep_tokens = int(token_count * ratio)

        # 编码后截断，再解码
        tokens = tokenizer.encode(content, disallowed_special=())
        truncated_tokens = tokens[:keep_tokens]
        truncated_content = tokenizer.decode(truncated_tokens)

        truncated.append((name, truncated_content))
        logger.warning(f"   - {name}: {token_count:,} → {keep_tokens:,} tokens ({ratio:.2%})")

    return truncated


def generate_tree_structure(folder_path: Path, explain_base: Path, max_depth: int = 2) -> str:
    """
    生成当前文件夹的目录树结构（用于在 prompt 中提供上下文）

    Args:
        folder_path: 当前文件夹路径（相对于 repo 根目录）
        explain_base: explain 输出的基础路径
        max_depth: 最大递归深度

    Returns:
        目录树的文本表示
    """
    explain_folder = explain_base / folder_path

    if not explain_folder.exists():
        return ""

    def build_tree(current_path: Path, prefix: str = "", depth: int = 0) -> list[str]:
        """递归构建树结构"""
        if depth >= max_depth:
            return []

        lines = []
        items = []

        # 收集所有项目（文件和文件夹）
        for item in sorted(current_path.iterdir()):
            if item.name == "README.md":
                continue
            items.append(item)

        for idx, item in enumerate(items):
            is_last = idx == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            next_prefix = prefix + ("    " if is_last else "│   ")

            if item.is_dir():
                lines.append(f"{prefix}{current_prefix}📁 {item.name}/")
                # 递归子目录
                lines.extend(build_tree(item, next_prefix, depth + 1))
            else:
                # 去掉 .md 后缀显示原始文件名
                display_name = item.name[:-3] if item.name.endswith(".md") else item.name
                lines.append(f"{prefix}{current_prefix}📄 {display_name}")

        return lines

    tree_lines = [f"📁 {folder_path if str(folder_path) != '.' else explain_base.parent.name}/"]
    tree_lines.extend(build_tree(explain_folder))

    return "\n".join(tree_lines)


def collect_folder_content(folder_path: Path, explain_base: Path) -> str:
    """
    收集文件夹下的所有内容（文件的 .md + 子文件夹的 README.md）

    Args:
        folder_path: 当前文件夹路径（相对于 repo 根目录）
        explain_base: explain 输出的基础路径

    Returns:
        合并后的内容字符串
    """
    explain_folder = explain_base / folder_path

    if not explain_folder.exists():
        return ""

    contents = []  # [(name, content, token_count), ...]

    # 收集直接子文件的 .md（不包括 README.md）
    for md_file in sorted(explain_folder.glob("*.md")):
        if md_file.name == "README.md":
            continue

        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            token_count = count_tokens(content)
            # 去掉 .md 后缀作为显示名称
            name = md_file.name[:-3] if md_file.name.endswith(".md") else md_file.name
            contents.append((f"📄 {name}", content, token_count))

    # 收集子文件夹的 README.md（截断以防止内容传播）
    for subfolder in sorted(explain_folder.iterdir()):
        if subfolder.is_dir():
            readme = subfolder / "README.md"
            if readme.exists():
                with open(readme, "r", encoding="utf-8") as f:
                    content = f.read()
                    token_count = count_tokens(content)
                    contents.append((f"📁 {subfolder.name}/", content, token_count))

    if not contents:
        return ""

    # 计算总 token 数
    total_tokens = sum(tc for _, _, tc in contents)

    # 如果超过限制，截断
    if total_tokens > MAX_TOKENS:
        contents_text = truncate_content(contents, MAX_TOKENS)
    else:
        contents_text = [(name, content) for name, content, _ in contents]

    # 拼接内容
    result = []
    for name, content in contents_text:
        result.append(f"## {name}\n\n{content}\n\n")

    return "".join(result)


async def ask_gemini_async(
    folder_path: str,
    content: str,
    tree_structure: str,
    client: AsyncOpenAI,
    model: str = "gemini-3-pro-preview"
) -> str:
    """
    异步调用 Gemini API 生成 README

    Args:
        folder_path: 文件夹路径
        content: 文件夹内容
        tree_structure: 目录树结构
        client: AsyncOpenAI 客户端
        model: 使用的模型

    Returns:
        README 内容（Markdown 格式）
    """
    prompt = README_PROMPT.format(
        folder_path=folder_path,
        tree_structure=tree_structure,
        content=content
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=32000,
            temperature=0.7,
        )

        finish_reason = response.choices[0].finish_reason
        content = response.choices[0].message.content or ""

        if finish_reason == "length":
            content += "\n\n_（注：响应因长度限制被截断）_"

        return content.strip()
    except Exception as e:
        return f"# README 生成失败\n\n错误信息: {str(e)}"


async def generate_readme_async(
    folder_path: Path,
    explain_base: Path,
    client: AsyncOpenAI,
    force: bool = False,
    model: str = "gemini-3-pro-preview",
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[Path, bool]:
    """
    异步生成单个文件夹的 README.md

    Args:
        folder_path: 当前文件夹路径（相对于 repo 根目录）
        explain_base: explain 输出的基础路径
        client: AsyncOpenAI 客户端
        force: 是否强制重新生成
        model: 使用的模型
        semaphore: 信号量，用于控制并发数

    Returns:
        (文件夹路径, 是否成功)
    """
    # 使用信号量控制并发
    if semaphore:
        async with semaphore:
            return await _generate_readme_impl(
                folder_path, explain_base, client, force, model
            )
    else:
        return await _generate_readme_impl(
            folder_path, explain_base, client, force, model
        )


async def _generate_readme_impl(
    folder_path: Path,
    explain_base: Path,
    client: AsyncOpenAI,
    force: bool,
    model: str,
) -> tuple[Path, bool]:
    """
    实际的 README 生成实现
    """
    explain_folder = explain_base / folder_path

    if not explain_folder.exists():
        return (folder_path, False)

    # 检查当前文件夹是否已有 README.md
    readme_path = explain_folder / "README.md"
    if readme_path.exists() and not force:
        return (folder_path, True)  # 跳过，视为成功

    # 收集当前文件夹的内容
    content = collect_folder_content(folder_path, explain_base)

    if not content:
        return (folder_path, False)

    # 生成目录树结构
    tree_structure = generate_tree_structure(folder_path, explain_base)

    # 调用 Gemini（异步）
    # 对于根目录，使用更有意义的名称
    folder_display_name = explain_base.parent.name if str(folder_path) == "." else str(folder_path)

    try:
        readme_content = await ask_gemini_async(folder_display_name, content, tree_structure, client, model)
    except Exception as e:
        logger.error(f"❌ API 调用失败 {folder_path}: {e}")
        return (folder_path, False)

    # 保存结果
    try:
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {folder_display_name}\n\n")
            f.write(readme_content)
        return (folder_path, True)
    except Exception as e:
        logger.error(f"❌ 保存失败 {folder_path}: {e}")
        return (folder_path, False)


def find_all_folders(explain_base: Path, root_folder: Path) -> list[Path]:
    """
    找到所有需要生成 README 的文件夹（自底向上排序）

    Args:
        explain_base: explain 输出的基础路径
        root_folder: 根文件夹（相对路径）

    Returns:
        文件夹路径列表（相对路径，按深度从深到浅排序）
    """
    explain_folder = explain_base / root_folder

    if not explain_folder.exists():
        return []

    folders = []

    def walk(current_path: Path):
        """递归遍历文件夹"""
        for item in current_path.iterdir():
            if item.is_dir():
                rel_path = item.relative_to(explain_base)
                folders.append(rel_path)
                walk(item)

    # 从根文件夹开始遍历
    folders.append(root_folder)
    walk(explain_folder)

    # 按深度从深到浅排序（深度 = 路径中的 / 数量）
    folders.sort(key=lambda p: len(p.parts), reverse=True)

    return folders


async def process_folders_batch(
    folders: list[Path],
    explain_base: Path,
    force: bool,
    model: str,
    max_workers: int = 8,
):
    """
    批量异步处理文件夹

    Args:
        folders: 文件夹列表（按深度从深到浅排序）
        explain_base: explain 输出的基础路径
        force: 是否强制重新生成
        model: 使用的模型
        max_workers: 最大并发数（默认 8）
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
        generate_readme_async(
            folder_path, explain_base, client, force, model, semaphore
        )
        for folder_path in folders
    ]

    # 使用 tqdm 异步进度条
    print(f"\n⚡ 使用 {max_workers} 个并发 worker 处理 {len(tasks)} 个文件夹")
    print()

    results = []
    for coro in async_tqdm.as_completed(tasks, desc="生成 README", unit="folder"):
        result = await coro
        results.append(result)

    # 统计结果
    success_count = sum(1 for _, success in results if success)
    return success_count, len(results)


async def main_async():
    """异步主函数"""
    parser = argparse.ArgumentParser(description="递归生成各层级目录的 README.md（异步版本）")
    parser.add_argument("repo_path", help="Git 仓库路径")
    parser.add_argument("--subdir", default="", help="要分析的子目录（默认为空，分析整个仓库）")
    parser.add_argument("--output", "-o", help="输出目录（默认：output/<repo_name>/explain）")
    parser.add_argument("--suffix", "-s", help="输出目录后缀（覆盖默认的日期后缀）")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    parser.add_argument("--model", "-m", default="gemini-3-pro-preview", help="使用的模型")
    parser.add_argument("--workers", "-w", type=int, default=8, help="最大并发数（默认：8）")

    args = parser.parse_args()

    # 默认输出路径：output/<repo_name>/explain-<date> 或 explain-<suffix>
    if args.output is None:
        repo_name = Path(args.repo_path).name
        if args.suffix:
            # 使用自定义后缀
            args.output = f"output/{repo_name}/explain-{args.suffix}"
        else:
            # 使用仓库名作为 subdir 参数传给 get_output_path
            args.output = get_output_path(args.repo_path, repo_name, "explain")

    explain_base = Path(args.output)

    # 如果 subdir 为空，使用 "." 表示根目录
    root_folder = Path(args.subdir) if args.subdir else Path(".")

    print(f"🚀 开始为 {args.subdir if args.subdir else '整个仓库'}/ 生成层级 README")
    print()

    # 找到所有文件夹（自底向上）
    folders = find_all_folders(explain_base, root_folder)

    if not folders:
        print("❌ 没有找到需要处理的文件夹")
        return

    print(f"📊 找到 {len(folders)} 个文件夹（自底向上）")
    print()

    # 异步批量处理
    success_count, total_count = await process_folders_batch(
        folders,
        explain_base,
        args.force,
        args.model,
        args.workers,
    )

    print(f"\n🎉 完成！成功生成 {success_count}/{total_count} 个 README")


def main():
    """同步入口，运行异步主函数"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
