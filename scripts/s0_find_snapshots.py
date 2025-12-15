#!/usr/bin/env python3
"""
S0 - Find Curriculum Learning Snapshots

通过 Claude Code 分析 git 历史，找出 3 个适合 curriculum learning 的快照点。
使用 `claude --print` 模式后台运行。

Usage:
    python scripts/s0_find_snapshots.py <repo_path>
    python scripts/s0_find_snapshots.py repo/flash-linear-attention
"""

import argparse
import subprocess
import json
import sys
from pathlib import Path

# 默认超时 50 分钟
DEFAULT_TIMEOUT = 3000

PROMPT_TEMPLATE = '''分析 {repo_path} 的 git 历史，确定 3 个适合 "Curriculum Learning" 的快照点。

任务：
1. 先查看这个 repo 是否有 version tags (git tag --list)
2. 查看 git log 的整体情况（总 commit 数、时间跨度）
3. 查看早期 commits (git log --oneline --reverse | head -50)
4. 查看各个 tag 或关键 commit 的文件数量
5. 识别关键里程碑 commits（如 "initial", "major refactor", "v1.0" 等）

选择原则：
- early: 项目核心架构建立时（文件数相对较少，但核心功能已有）
- mid: 功能扩展的中间阶段（有实质性功能增长）
- current: 就是 HEAD

输出要求：
只输出 JSON，不要其他文字。格式如下：
```json
{{
  "repo_name": "仓库名",
  "snapshots": [
    {{"stage": "early", "commit_hash": "完整hash", "date": "YYYY-MM-DD", "file_count": N, "reason": "为什么选这个点"}},
    {{"stage": "mid", "commit_hash": "完整hash", "date": "YYYY-MM-DD", "file_count": N, "reason": "为什么选这个点"}},
    {{"stage": "current", "commit_hash": "完整hash", "date": "YYYY-MM-DD", "file_count": N, "reason": "为什么选这个点"}}
  ],
  "analysis_summary": "整体分析说明"
}}
```

注意：commit_hash 必须是完整的 40 字符 hash，不是短 hash。'''


def find_snapshots(
    repo_path: str,
    output_path: str = None,
    verbose: bool = False,
    timeout: int = DEFAULT_TIMEOUT
) -> dict:
    """
    使用 Claude Code 分析 repo 的 git history，找出 3 个快照点。

    Args:
        repo_path: 仓库路径
        output_path: 输出 JSON 文件路径，默认为 repo_path/snapshots.json
        verbose: 是否显示详细输出
        timeout: 超时时间（秒）

    Returns:
        包含快照信息的字典
    """
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    if not (repo_path / ".git").exists():
        raise ValueError(f"Not a git repository: {repo_path}")

    # 默认输出路径
    if output_path is None:
        output_path = repo_path / "snapshots.json"
    else:
        output_path = Path(output_path)

    repo_name = repo_path.name
    prompt = PROMPT_TEMPLATE.format(repo_path=repo_path)

    print(f"🔍 分析仓库: {repo_name}")
    print(f"📂 路径: {repo_path}")
    print(f"⏱️  超时: {timeout}s")
    print(f"⏳ 正在调用 Claude Code 分析 git 历史...")

    # 调用 claude --print 模式
    cmd = [
        "claude",
        "--print",
        "--output-format", "text",
        "--dangerously-skip-permissions",  # 跳过权限检查，因为只是读取 git 信息
        prompt
    ]

    if verbose:
        print(f"📋 命令: {' '.join(cmd[:5])}...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(repo_path),  # 在 repo 目录下运行
            timeout=timeout
        )

        if result.returncode != 0:
            print(f"❌ Claude Code 执行失败:")
            print(result.stderr)
            sys.exit(1)

        output = result.stdout.strip()

        if verbose:
            print("\n--- Raw Output ---")
            print(output)
            print("--- End Output ---\n")

        # 提取 JSON（可能被 markdown 代码块包裹）
        json_str = extract_json(output)

        if not json_str:
            print("❌ 无法从输出中提取 JSON")
            print("原始输出:")
            print(output)
            sys.exit(1)

        # 解析 JSON
        data = json.loads(json_str)

        # 保存到文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ 分析完成！")
        print(f"📄 结果已保存到: {output_path}")

        # 打印摘要
        print_summary(data)

        return data

    except subprocess.TimeoutExpired:
        print(f"❌ 分析超时（{timeout}秒）")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        print("原始输出:")
        print(output)
        sys.exit(1)


def extract_json(text: str) -> str:
    """从文本中提取 JSON 字符串"""
    # 尝试直接解析
    text = text.strip()
    if text.startswith('{'):
        # 找到最后一个 }
        depth = 0
        end_idx = 0
        for i, c in enumerate(text):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        return text[:end_idx]

    # 尝试从 markdown 代码块中提取
    import re

    # 匹配 ```json ... ``` 或 ``` ... ```
    patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
        r'```json(.*?)```',
        r'```(.*?)```',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

    # 尝试找到 { 开始的 JSON
    start = text.find('{')
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]

    return None


def print_summary(data: dict):
    """打印分析摘要"""
    print("\n" + "="*60)
    print(f"📊 {data.get('repo_name', 'Unknown')} 快照切分")
    print("="*60)

    for snapshot in data.get('snapshots', []):
        stage = snapshot.get('stage', '?')
        date = snapshot.get('date', '?')
        file_count = snapshot.get('file_count', '?')
        commit = snapshot.get('commit_hash', '?')[:8]
        reason = snapshot.get('reason', '')[:60]

        emoji = {'early': '🌱', 'mid': '🌿', 'current': '🌳'}.get(stage, '📍')
        print(f"\n{emoji} {stage.upper()}")
        print(f"   Commit: {commit}...")
        print(f"   Date:   {date}")
        print(f"   Files:  {file_count}")
        print(f"   Reason: {reason}...")

    print("\n" + "="*60)
    summary = data.get('analysis_summary', '')
    if summary:
        # 截取前 200 字符
        if len(summary) > 200:
            summary = summary[:200] + "..."
        print(f"📝 {summary}")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="通过 Claude Code 分析 git 历史，找出 curriculum learning 的快照点"
    )
    parser.add_argument(
        "repo_path",
        help="仓库路径 (例如: repo/flash-linear-attention)"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出 JSON 文件路径 (默认: <repo_path>/snapshots.json)"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"超时时间（秒）(默认: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细输出"
    )

    args = parser.parse_args()

    find_snapshots(
        repo_path=args.repo_path,
        output_path=args.output,
        verbose=args.verbose,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
