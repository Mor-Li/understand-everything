#!/usr/bin/env python3
"""
S1 - Curriculum Learning Pipeline

根据 snapshots.json 对仓库进行多阶段（early/mid/current）的完整文档生成流程。

Usage:
    python scripts/s1_curriculum_pipeline.py <repo_path>
    python scripts/s1_curriculum_pipeline.py repo/flash-linear-attention --workers 16

Pipeline:
    1. 读取 snapshots.json
    2. 对每个 snapshot (early, mid, current):
       - git checkout <commit_hash>
       - 运行 s2_explain_files.py --suffix <stage>
       - 运行 s3_generate_readme.py --suffix <stage>
       - 运行 s4_website.py --suffix <stage>
    3. git checkout main (恢复)
    4. 生成版本选择器 output/<repo>/index.html
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import git


# 版本选择器页面模板 - 简约优雅风格
VERSION_INDEX_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{repo_name} - Curriculum Learning</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #fafafa;
            min-height: 100vh;
            padding: 60px 20px;
            color: #1a1a1a;
        }}
        .container {{
            max-width: 720px;
            margin: 0 auto;
        }}
        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: #666;
            text-decoration: none;
            font-size: 0.9rem;
            margin-bottom: 40px;
            transition: color 0.2s;
        }}
        .back-link:hover {{ color: #1a1a1a; }}
        .header {{
            margin-bottom: 48px;
        }}
        .header h1 {{
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 8px;
            letter-spacing: -0.02em;
        }}
        .header p {{
            color: #666;
            font-size: 1rem;
        }}
        .timeline {{
            position: relative;
            padding-left: 24px;
        }}
        .timeline::before {{
            content: '';
            position: absolute;
            left: 5px;
            top: 8px;
            bottom: 8px;
            width: 2px;
            background: #e5e5e5;
        }}
        .version-card {{
            background: #fff;
            border: 1px solid #eaeaea;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            position: relative;
            transition: all 0.2s ease;
            cursor: pointer;
            text-decoration: none;
            display: block;
            color: inherit;
        }}
        .version-card:hover {{
            border-color: #ccc;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        .version-card::before {{
            content: '';
            position: absolute;
            left: -22px;
            top: 24px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #fff;
            border: 2px solid #ddd;
        }}
        .version-card.early::before {{ border-color: #22c55e; background: #dcfce7; }}
        .version-card.mid::before {{ border-color: #eab308; background: #fef9c3; }}
        .version-card.current::before {{ border-color: #3b82f6; background: #dbeafe; }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .stage-badge {{
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }}
        .stage-badge.early {{ background: #dcfce7; color: #166534; }}
        .stage-badge.mid {{ background: #fef9c3; color: #854d0e; }}
        .stage-badge.current {{ background: #dbeafe; color: #1e40af; }}
        .stage-badge.other {{ background: #f5f5f5; color: #525252; }}
        .date {{ color: #999; font-size: 0.85rem; }}
        .card-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .card-meta {{
            display: flex;
            gap: 16px;
            color: #666;
            font-size: 0.85rem;
        }}
        .card-reason {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #f0f0f0;
            color: #555;
            font-size: 0.9rem;
            line-height: 1.6;
        }}
        @media (max-width: 600px) {{
            body {{ padding: 40px 16px; }}
            .header h1 {{ font-size: 1.6rem; }}
            .version-card {{ padding: 16px 20px; }}
            .card-meta {{ flex-direction: column; gap: 4px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <a href="../../index.html" class="back-link">← 返回项目列表</a>

        <div class="header">
            <h1>{repo_name}</h1>
            <p>渐进式代码理解 · Curriculum Learning</p>
        </div>

        <div class="timeline">
            {version_cards}
        </div>
    </div>
</body>
</html>'''

VERSION_CARD_TEMPLATE = '''
            <a href="{website_path}/index.html" class="version-card {stage_class}">
                <div class="card-header">
                    <span class="stage-badge {stage_class}">{stage_label}</span>
                    <span class="date">{date}</span>
                </div>
                <div class="card-title">{title}</div>
                <div class="card-meta">
                    <span>📁 {file_count} 文件</span>
                    <span>🔗 {commit_short}</span>
                </div>
                <div class="card-reason">{reason}</div>
            </a>'''


def generate_version_index(repo_name: str, snapshots: list[dict], output_base: Path):
    """
    生成版本选择器页面 output/<repo>/index.html
    """
    stage_labels = {
        'early': '🌱 早期',
        'mid': '🌿 中期',
        'current': '🌳 当前',
    }

    stage_titles = {
        'early': '项目早期 - 核心架构建立',
        'mid': '项目中期 - 功能扩展阶段',
        'current': '当前版本 - 完整功能',
    }

    # 按时间顺序排序（early -> mid -> current）
    stage_order = {'early': 0, 'mid': 1, 'current': 2}
    sorted_snapshots = sorted(
        snapshots,
        key=lambda s: stage_order.get(s.get('stage', 'other'), 99)
    )

    version_cards = []
    for snapshot in sorted_snapshots:
        stage = snapshot.get('stage', 'other')
        stage_class = stage if stage in ['early', 'mid', 'current'] else 'other'

        # 使用日期作为路径，而不是 stage 名称
        date = snapshot.get('date', 'Unknown')
        card = VERSION_CARD_TEMPLATE.format(
            website_path=f"website-{date}",
            stage_class=stage_class,
            stage_label=stage_labels.get(stage, stage.upper()),
            date=date,
            title=stage_titles.get(stage, f'{stage} 版本'),
            file_count=snapshot.get('file_count', '?'),
            commit_short=snapshot.get('commit_hash', '')[:8],
            reason=snapshot.get('reason', ''),
        )
        version_cards.append(card)

    html_content = VERSION_INDEX_TEMPLATE.format(
        repo_name=repo_name,
        version_cards=''.join(version_cards)
    )

    output_base.mkdir(parents=True, exist_ok=True)
    index_file = output_base / "index.html"
    index_file.write_text(html_content, encoding='utf-8')
    print(f"✓ 版本选择器已生成: {index_file}")


def load_snapshots(repo_path: Path) -> dict:
    """加载 snapshots.json"""
    snapshots_file = repo_path / "snapshots.json"
    if not snapshots_file.exists():
        raise FileNotFoundError(
            f"snapshots.json not found in {repo_path}\n"
            f"Please run: python scripts/s0_find_snapshots.py {repo_path}"
        )

    with open(snapshots_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_command(cmd: list[str], cwd: str = None, description: str = None):
    """运行命令并显示输出"""
    if description:
        print(f"\n{'='*60}")
        print(f"🔧 {description}")
        print(f"{'='*60}")
        print(f"$ {' '.join(cmd[:5])}{'...' if len(cmd) > 5 else ''}")

    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=False,  # 直接显示输出
    )

    if result.returncode != 0:
        print(f"❌ Command failed with code {result.returncode}")
        return False
    return True


def process_snapshot(
    repo_path: Path,
    snapshot: dict,
    workers: int,
    percent: int,
    force: bool,
    scripts_dir: Path,
):
    """处理单个 snapshot"""
    stage = snapshot['stage']
    commit_hash = snapshot['commit_hash']
    date = snapshot['date']  # 使用日期作为后缀
    file_count = snapshot.get('file_count', '?')

    print(f"\n{'#'*60}")
    print(f"# Stage: {stage.upper()} ({date})")
    print(f"# Commit: {commit_hash[:8]}...")
    print(f"# Date: {date}")
    print(f"# Files: {file_count}")
    print(f"{'#'*60}")

    # 1. Checkout to commit
    repo = git.Repo(repo_path)
    original_head = repo.head.commit.hexsha

    print(f"\n📍 Checking out to {commit_hash[:8]}...")
    try:
        repo.git.checkout(commit_hash)
    except git.GitCommandError as e:
        print(f"❌ Checkout failed: {e}")
        return False

    try:
        # 2. Run s2_explain_files.py (使用日期作为后缀)
        s1_cmd = [
            sys.executable,
            str(scripts_dir / "s2_explain_files.py"),
            str(repo_path),
            "--suffix", date,
            "--workers", str(workers),
            "--percent", str(percent),
        ]
        if force:
            s1_cmd.append("--force")

        if not run_command(s1_cmd, description=f"S2: Explain files for {stage} ({date})"):
            return False

        # 3. Run s3_generate_readme.py
        s2_cmd = [
            sys.executable,
            str(scripts_dir / "s3_generate_readme.py"),
            str(repo_path),
            "--suffix", date,
            "--workers", str(workers),
        ]
        if force:
            s2_cmd.append("--force")

        if not run_command(s2_cmd, description=f"S3: Generate README for {stage} ({date})"):
            return False

        # 4. Run s4_website.py
        s3_cmd = [
            sys.executable,
            str(scripts_dir / "s4_website.py"),
            str(repo_path),
            "--suffix", date,
        ]

        if not run_command(s3_cmd, description=f"S4: Generate website for {stage} ({date})"):
            return False

        return True

    finally:
        # 5. Checkout back to original
        print(f"\n📍 Restoring to original HEAD ({original_head[:8]})...")
        try:
            repo.git.checkout(original_head)
        except git.GitCommandError as e:
            print(f"⚠️  Failed to restore HEAD: {e}")
            print(f"   Please manually run: git checkout main")


def main():
    parser = argparse.ArgumentParser(
        description="Curriculum Learning Pipeline - 对仓库进行多阶段文档生成"
    )
    parser.add_argument(
        "repo_path",
        help="仓库路径 (需要已存在 snapshots.json)"
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        default=["early", "mid", "current"],
        help="要处理的阶段 (默认: early mid current)"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=16,
        help="并发 worker 数量 (默认: 16)"
    )
    parser.add_argument(
        "-p", "--percent",
        type=int,
        default=100,
        help="处理文件的百分比 (默认: 100)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成"
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    scripts_dir = Path(__file__).parent

    if not repo_path.exists():
        print(f"❌ Repository not found: {repo_path}")
        sys.exit(1)

    if not (repo_path / ".git").exists():
        print(f"❌ Not a git repository: {repo_path}")
        sys.exit(1)

    # Load snapshots
    print(f"📂 Loading snapshots from {repo_path / 'snapshots.json'}")
    try:
        data = load_snapshots(repo_path)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    repo_name = data.get('repo_name', repo_path.name)
    snapshots = data.get('snapshots', [])

    print(f"\n🚀 Curriculum Learning Pipeline for: {repo_name}")
    print(f"   Stages to process: {args.stages}")
    print(f"   Workers: {args.workers}")
    print(f"   Percent: {args.percent}%")

    # Filter snapshots by requested stages
    snapshots_to_process = [
        s for s in snapshots
        if s.get('stage') in args.stages
    ]

    if not snapshots_to_process:
        print(f"❌ No snapshots found for stages: {args.stages}")
        sys.exit(1)

    print(f"\n📊 Found {len(snapshots_to_process)} snapshots to process:")
    for s in snapshots_to_process:
        print(f"   - {s['stage']}: {s['commit_hash'][:8]} ({s['date']}, {s.get('file_count', '?')} files)")

    # Process each snapshot
    success_count = 0
    for snapshot in snapshots_to_process:
        if process_snapshot(
            repo_path,
            snapshot,
            args.workers,
            args.percent,
            args.force,
            scripts_dir
        ):
            success_count += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"🎉 Pipeline complete!")
    print(f"   Success: {success_count}/{len(snapshots_to_process)} stages")
    print(f"{'='*60}")

    # Show output locations (使用日期作为路径)
    print(f"\n📁 Output locations:")
    for s in snapshots_to_process:
        stage = s['stage']
        date = s['date']
        print(f"   {stage} ({date}):")
        print(f"      explain:  output/{repo_name}/explain-{date}/")
        print(f"      website:  output/{repo_name}/website-{date}/")

    # Generate version selector index.html
    if success_count > 0:
        print(f"\n📝 生成版本选择器页面...")
        output_base = Path("output") / repo_name
        generate_version_index(repo_name, snapshots_to_process, output_base)

    if success_count < len(snapshots_to_process):
        sys.exit(1)


if __name__ == "__main__":
    main()
