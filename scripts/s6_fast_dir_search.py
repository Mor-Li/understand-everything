"""
s6_fast_dir_search.py
高效多进程目录搜索工具 - 在 /mnt/moonfs 下搜索指定名称的目录

特点：
- 多进程并行扫描，最大化搜索速度
- 只扫描目录名称，不读取文件内容
- 实时进度条显示
- 支持自定义搜索深度和并发数
"""

import argparse
import os
from multiprocessing import Manager, Pool, cpu_count
from pathlib import Path

from tqdm import tqdm


def scan_directory_batch(args):
    """
    批量扫描目录（单个进程执行）

    Args:
        args: (dirs_to_scan, target_name, max_depth, results_list, progress_queue)

    Returns:
        找到的匹配目录列表
    """
    dirs_to_scan, target_name, max_depth, results_list, progress_queue = args
    local_matches = []

    for dir_path, current_depth in dirs_to_scan:
        try:
            # 跳过符号链接和不可访问的目录
            if os.path.islink(dir_path) or not os.access(dir_path, os.R_OK | os.X_OK):
                progress_queue.put(1)
                continue

            # 检查当前目录名是否匹配
            dir_name = os.path.basename(dir_path)
            if dir_name == target_name:
                local_matches.append(dir_path)

            # 如果未达到最大深度，扫描子目录
            if current_depth < max_depth:
                try:
                    with os.scandir(dir_path) as entries:
                        for entry in entries:
                            if entry.is_dir(follow_symlinks=False):
                                # 立即检查子目录名称
                                if entry.name == target_name:
                                    local_matches.append(entry.path)
                except (PermissionError, OSError):
                    pass

            progress_queue.put(1)

        except (PermissionError, OSError):
            progress_queue.put(1)
            continue

    return local_matches


def parallel_search(root_dir, target_name, max_depth=10, num_workers=None):
    """
    并行搜索目录

    Args:
        root_dir: 根目录路径
        target_name: 要搜索的目录名称
        max_depth: 最大搜索深度
        num_workers: 工作进程数（None = CPU 核心数）

    Returns:
        找到的匹配目录列表
    """
    if num_workers is None:
        num_workers = max(cpu_count(), 8)  # 至少使用 8 个进程

    print(f"🚀 开始搜索: {root_dir}")
    print(f"🎯 目标目录: {target_name}")
    print(f"📊 最大深度: {max_depth}")
    print(f"⚡ 工作进程: {num_workers}")
    print()

    # 使用 Manager 创建共享列表和队列
    manager = Manager()
    results_list = manager.list()
    progress_queue = manager.Queue()

    # 第一阶段：快速扫描顶层目录，收集所有一级子目录
    first_level_dirs = []
    try:
        with os.scandir(root_dir) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    # 检查顶层目录名称
                    if entry.name == target_name:
                        results_list.append(entry.path)
                    first_level_dirs.append((entry.path, 1))
    except (PermissionError, OSError) as e:
        print(f"❌ 无法访问 {root_dir}: {e}")
        return []

    if not first_level_dirs:
        print("⚠️  没有可访问的子目录")
        return list(results_list)

    print(f"📁 找到 {len(first_level_dirs)} 个顶层目录")
    print()

    # 第二阶段：将一级子目录分批分配给多个进程
    # 每个进程处理一批目录
    batch_size = max(1, len(first_level_dirs) // (num_workers * 4))  # 每个进程处理多批次
    batches = []

    for i in range(0, len(first_level_dirs), batch_size):
        batch = first_level_dirs[i:i + batch_size]
        batches.append((batch, target_name, max_depth, results_list, progress_queue))

    print(f"🔄 分成 {len(batches)} 个批次并行处理")
    print()

    # 启动进度条
    total_dirs = len(first_level_dirs)

    # 使用进程池并行处理
    with Pool(processes=num_workers) as pool:
        # 异步提交所有任务
        async_results = [pool.apply_async(scan_directory_batch, (batch,)) for batch in batches]

        # 实时更新进度条
        with tqdm(total=total_dirs, desc="扫描进度", unit="dir") as pbar:
            processed = 0
            while processed < total_dirs:
                # 非阻塞获取进度更新
                try:
                    progress_queue.get(timeout=0.1)
                    processed += 1
                    pbar.update(1)
                except Exception:
                    pass

        # 收集所有结果
        all_matches = []
        for async_result in async_results:
            try:
                matches = async_result.get(timeout=1)
                all_matches.extend(matches)
            except Exception:
                pass

    # 合并共享列表中的结果
    all_matches.extend(list(results_list))

    # 去重
    return sorted(set(all_matches))


def _scan_second_level_worker(dir_path_and_target):
    """
    工作函数：扫描第二层目录（必须在模块级别以支持 pickle）
    """
    dir_path, target_name = dir_path_and_target
    local_matches = []
    try:
        if os.access(dir_path, os.R_OK | os.X_OK):
            with os.scandir(dir_path) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name == target_name:
                            local_matches.append(entry.path)
    except (PermissionError, OSError):
        pass
    return local_matches


def fast_shallow_search(root_dir, target_name, num_workers=None):
    """
    快速浅层搜索（只搜索前 2 层）

    适用于目录结构已知、目标目录通常在浅层的场景
    """
    if num_workers is None:
        num_workers = max(cpu_count(), 8)

    print("⚡ 快速模式：只搜索前 2 层目录")
    print()

    matches = []

    # 扫描第一层
    try:
        with os.scandir(root_dir) as entries:
            first_level = []
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name == target_name:
                        matches.append(entry.path)
                    first_level.append(entry.path)
    except (PermissionError, OSError) as e:
        print(f"❌ 无法访问 {root_dir}: {e}")
        return []

    print(f"📁 第 1 层: {len(first_level)} 个目录")

    # 并行扫描第二层
    tasks = [(path, target_name) for path in first_level]

    with Pool(processes=num_workers) as pool:
        results = list(tqdm(
            pool.imap_unordered(_scan_second_level_worker, tasks),
            total=len(tasks),
            desc="扫描第 2 层",
            unit="dir"
        ))

    for result in results:
        matches.extend(result)

    return sorted(set(matches))


def main():
    parser = argparse.ArgumentParser(
        description="高效多进程目录搜索工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜索 Megatron-LM 目录（默认深度 10）
  python s6_fast_dir_search.py Megatron-LM

  # 使用快速模式（只搜索前 2 层）
  python s6_fast_dir_search.py Megatron-LM --fast

  # 自定义搜索深度和进程数
  python s6_fast_dir_search.py Megatron-LM --max-depth 5 --workers 16

  # 在其他目录搜索
  python s6_fast_dir_search.py checkpoints --root /mnt/moonfs/limo-m3
        """
    )

    parser.add_argument("target", help="要搜索的目录名称")
    parser.add_argument(
        "--root",
        default="/mnt/moonfs",
        help="搜索根目录（默认: /mnt/moonfs）"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="最大搜索深度（默认: 10）"
    )
    parser.add_argument(
        "--workers",
        type=int,
        help=f"工作进程数（默认: CPU 核心数，当前系统: {cpu_count()}）"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="快速模式：只搜索前 2 层目录"
    )

    args = parser.parse_args()

    root_dir = Path(args.root)

    if not root_dir.exists():
        print(f"❌ 目录不存在: {root_dir}")
        return

    if not root_dir.is_dir():
        print(f"❌ 不是目录: {root_dir}")
        return

    print("=" * 70)
    print("🔍 高效目录搜索工具")
    print("=" * 70)
    print()

    # 执行搜索
    if args.fast:
        matches = fast_shallow_search(str(root_dir), args.target, args.workers)
    else:
        matches = parallel_search(
            str(root_dir),
            args.target,
            args.max_depth,
            args.workers
        )

    print()
    print("=" * 70)
    print("✨ 搜索完成")
    print("=" * 70)
    print()

    if matches:
        print(f"🎉 找到 {len(matches)} 个匹配的目录:")
        print()
        for i, match in enumerate(matches, 1):
            print(f"  {i}. {match}")
    else:
        print(f"😔 未找到名为 '{args.target}' 的目录")


if __name__ == "__main__":
    main()
