"""
s4_generate_readme.py
递归生成各层级目录的 README.md（自底向上）
"""

import argparse
import logging
import os
from pathlib import Path

import tiktoken
from openai import OpenAI
from tqdm import tqdm

from utils import get_output_path

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
README_PROMPT = """以下是 {folder_path} 目录下的内容：

{content}

请你用最通俗易懂的语言、用比喻的方式描述一下：
1. 当前这个文件夹主要负责什么功能？
2. 这个文件夹下的各个文件/子文件夹分别是干什么的？
3. 给我一个高层的认知，让我能快速理解这部分代码的作用。

请用简洁、通俗、易懂的语气回答，说中文。"""


def count_tokens(text: str) -> int:
    """计算文本的 token 数量"""
    return len(tokenizer.encode(text))


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
        tokens = tokenizer.encode(content)
        truncated_tokens = tokens[:keep_tokens]
        truncated_content = tokenizer.decode(truncated_tokens)

        truncated.append((name, truncated_content))
        logger.warning(f"   - {name}: {token_count:,} → {keep_tokens:,} tokens ({ratio:.2%})")

    return truncated


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

    # 收集子文件夹的 README.md
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


def ask_gemini(folder_path: str, content: str, model: str = "gemini-3-pro-preview") -> str:
    """
    调用 Gemini API 生成 README

    Args:
        folder_path: 文件夹路径
        content: 文件夹内容
        model: 使用的模型

    Returns:
        README 内容（Markdown 格式）
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError("需要设置环境变量 OPENAI_API_KEY")

    client = OpenAI(api_key=api_key, base_url=base_url)

    prompt = README_PROMPT.format(folder_path=folder_path, content=content)

    try:
        response = client.chat.completions.create(
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


def generate_readme_recursive(
    folder_path: Path,
    explain_base: Path,
    force: bool = False,
    model: str = "gemini-3-pro-preview",
) -> bool:
    """
    递归生成 README.md（自底向上）

    Args:
        folder_path: 当前文件夹路径（相对于 repo 根目录）
        explain_base: explain 输出的基础路径
        force: 是否强制重新生成
        model: 使用的模型

    Returns:
        是否成功
    """
    explain_folder = explain_base / folder_path

    if not explain_folder.exists():
        return False

    # 先递归处理所有子文件夹
    for subfolder in sorted(explain_folder.iterdir()):
        if subfolder.is_dir():
            sub_rel_path = folder_path / subfolder.name
            generate_readme_recursive(sub_rel_path, explain_base, force, model)

    # 检查当前文件夹是否已有 README.md
    readme_path = explain_folder / "README.md"
    if readme_path.exists() and not force:
        logger.info(f"⏭️  跳过 {folder_path}（已存在 README.md）")
        return True

    # 收集当前文件夹的内容
    content = collect_folder_content(folder_path, explain_base)

    if not content:
        logger.info(f"⏭️  跳过 {folder_path}（没有内容）")
        return False

    # 调用 Gemini 生成 README
    logger.info(f"🤖 正在生成 {folder_path} 的 README...")
    readme_content = ask_gemini(str(folder_path), content, model)

    # 保存 README.md
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"# {folder_path}\n\n")
        f.write(readme_content)

    logger.info(f"✓ 已保存到 {readme_path}")
    return True


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


def main():
    parser = argparse.ArgumentParser(description="递归生成各层级目录的 README.md")
    parser.add_argument("repo_path", help="Git 仓库路径")
    parser.add_argument("--subdir", default="mshrl", help="要分析的子目录")
    parser.add_argument("--output", "-o", help="输出目录（默认：output/<repo_name>/explain）")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    parser.add_argument("--model", "-m", default="gemini-3-pro-preview", help="使用的模型")

    args = parser.parse_args()

    # 默认输出路径：output/<repo_name>/explain-<date>
    if args.output is None:
        args.output = get_output_path(args.repo_path, args.subdir, "explain")

    explain_base = Path(args.output)
    root_folder = Path(args.subdir)

    print(f"🚀 开始为 {args.subdir}/ 生成层级 README")
    print()

    # 找到所有文件夹（自底向上）
    folders = find_all_folders(explain_base, root_folder)

    if not folders:
        print("❌ 没有找到需要处理的文件夹")
        return

    print(f"📊 找到 {len(folders)} 个文件夹（自底向上）")
    print()

    # 逐个生成 README（带进度条）
    success_count = 0
    with tqdm(total=len(folders), desc="生成 README", unit="folder") as pbar:
        for folder_path in folders:
            if generate_readme_recursive(folder_path, explain_base, args.force, args.model):
                success_count += 1
            pbar.update(1)

    print(f"\n🎉 完成！成功生成 {success_count}/{len(folders)} 个 README")


if __name__ == "__main__":
    main()
