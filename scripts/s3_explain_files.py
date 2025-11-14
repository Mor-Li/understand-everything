"""
s2_explain_files.py
使用 Gemini API 对代码文件进行通俗易懂的解释
"""

import argparse
import os
from collections import defaultdict
from pathlib import Path

import git
from openai import OpenAI
from tqdm import tqdm


# Prompt 模板
EXPLAIN_PROMPT = """这个我完全看不懂讲的啥 你觉得能不能列一个list 列一个task的todo 逐渐的给我一步一步讲讲文中的观点。请说中文

文件路径: {file_path}

文件内容:
```
{file_content}
```"""


def ask_gemini(file_path: str, file_content: str, model: str = "gemini-2.5-pro") -> str:
    """
    调用 Gemini API 解释文件内容

    Args:
        file_path: 文件路径
        file_content: 文件内容
        model: 使用的模型

    Returns:
        解释文本（Markdown 格式）
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise ValueError("需要设置环境变量 OPENAI_API_KEY")

    client = OpenAI(api_key=api_key, base_url=base_url)

    prompt = EXPLAIN_PROMPT.format(file_path=file_path, file_content=file_content)

    try:
        response = client.chat.completions.create(
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


def get_top_files(repo_path: str, subdir: str, top_n: int = None) -> list[tuple[str, int]]:
    """
    获取指定子目录下修改次数最多的文件（按修改次数排序）

    Args:
        repo_path: 仓库路径
        subdir: 子目录（相对于仓库根目录）
        top_n: 返回前 N 个文件，None 表示返回全部

    Returns:
        [(相对文件路径, 修改次数), ...] 列表（已按修改次数降序排序）
    """
    repo = git.Repo(repo_path)
    file_change_count = defaultdict(int)

    print(f"📊 分析 {subdir}/ 下的文件修改历史...")

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


def explain_file(
    repo_path: str,
    file_rel_path: str,
    output_base: str,
    force: bool = False,
    model: str = "gemini-2.5-pro",
) -> bool:
    """
    解释单个文件并保存为 Markdown

    Args:
        repo_path: 仓库路径
        file_rel_path: 文件相对路径（相对于仓库根目录）
        output_base: 输出基础目录
        force: 是否强制重新生成
        model: 使用的模型

    Returns:
        是否成功
    """
    # 构建输入输出路径
    repo_root = Path(repo_path)
    input_file = repo_root / file_rel_path
    output_file = Path(output_base) / (file_rel_path + ".md")

    # 检查是否已存在
    if output_file.exists() and not force:
        print(f"⏭️  跳过 {file_rel_path}（已存在解释文件）")
        return True

    # 读取文件内容
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取失败 {file_rel_path}: {e}")
        return False

    # 调用 Gemini
    print(f"🤖 正在解释 {file_rel_path}...")
    explanation = ask_gemini(file_rel_path, content, model)

    # 保存结果
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {file_rel_path}\n\n")
        f.write(explanation)

    print(f"✓ 已保存到 {output_file}")
    return True


def main():
    parser = argparse.ArgumentParser(description="解释代码文件")
    parser.add_argument("repo_path", help="Git 仓库路径")
    parser.add_argument("--subdir", default="mshrl", help="要分析的子目录")
    parser.add_argument("--top", type=int, help="解释 top N 个文件（与 --percent 互斥）")
    parser.add_argument("--percent", type=int, help="解释前 N%% 的文件（按修改次数排序，与 --top 互斥）")
    parser.add_argument("--output", "-o", help="输出目录（默认：output/<repo_name>/explain）")
    parser.add_argument("--force", action="store_true", help="强制重新生成")
    parser.add_argument("--model", "-m", default="gemini-2.5-pro", help="使用的模型")

    args = parser.parse_args()

    # 获取仓库名称
    repo_name = Path(args.repo_path).name

    # 默认输出路径：output/<repo_name>/explain
    if args.output is None:
        args.output = f"output/{repo_name}/explain"

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
        print(f"🚀 开始解释 {args.repo_path}/{args.subdir}/ 下前 {args.percent}% 的文件 ({n_files}/{len(all_files)} 个)")
    else:
        selected_files = all_files[:args.top]
        print(f"🚀 开始解释 {args.repo_path}/{args.subdir}/ 下的 top {args.top} 文件")

    # 显示选中的文件
    print()
    for i, (file_path, count) in enumerate(selected_files, 1):
        print(f"   {i}. {file_path} ({count} 次修改)")
    print()

    # 逐个解释（带进度条）
    success_count = 0
    with tqdm(total=len(selected_files), desc="解释文件", unit="file") as pbar:
        for file_rel_path, change_count in selected_files:
            if explain_file(args.repo_path, file_rel_path, args.output, args.force, args.model):
                success_count += 1
            pbar.update(1)

    print(f"\n🎉 完成！成功解释 {success_count}/{len(selected_files)} 个文件")


if __name__ == "__main__":
    main()
