"""
s1_repo_heatmap_tree.py
生成仓库结构的热力图树状图
- 最大深度：5 层
- 每个目录最多显示：20 个文件
- 颜色：根据 git 历史中文件被修改的频率（越红 = 修改越频繁）
- figure size：自适应
"""

import argparse
from collections import defaultdict
from pathlib import Path

import git
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np


class RepoTreeHeatmap:
    def __init__(self, repo_path: str, max_depth: int = 5, max_files_per_dir: int = 20):
        self.repo_path = Path(repo_path)
        self.repo = git.Repo(repo_path)
        self.max_depth = max_depth
        self.max_files_per_dir = max_files_per_dir
        self.file_change_count = defaultdict(int)
        self.total_lines = 0  # 记录总行数，用于计算高度

    def collect_file_changes(self):
        """统计每个文件在 git 历史中被修改的次数"""
        print("📊 正在分析 git 历史...")

        for commit in self.repo.iter_commits():
            try:
                if commit.parents:
                    diffs = commit.parents[0].diff(commit)
                    for diff in diffs:
                        # 获取文件路径
                        file_path = diff.a_path or diff.b_path
                        if file_path:
                            self.file_change_count[file_path] += 1
            except Exception as e:
                continue

        print(f"✓ 分析完成，共 {len(self.file_change_count)} 个文件有修改记录")

    def build_tree_structure(self):
        """构建树状结构（限制深度和每层文件数）"""
        print("🌲 正在构建树状结构...")

        tree = {}

        # 只包含当前存在的文件
        for file_path in self.repo_path.rglob("*"):
            if file_path.is_file() and ".git" not in str(file_path):
                rel_path = file_path.relative_to(self.repo_path)
                parts = rel_path.parts

                # 检查深度
                if len(parts) > self.max_depth:
                    continue

                # 构建树
                current = tree
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:  # 文件
                        if "files" not in current:
                            current["files"] = []
                        current["files"].append(part)
                    else:  # 目录
                        if "dirs" not in current:
                            current["dirs"] = {}
                        if part not in current["dirs"]:
                            current["dirs"][part] = {}
                        current = current["dirs"][part]

        # 限制每个目录的文件数量
        self._limit_files(tree)

        print(f"✓ 树状结构构建完成")
        return tree

    def _limit_files(self, tree):
        """递归限制每个目录的文件数量"""
        if "files" in tree:
            # 按修改频率排序，保留最常修改的文件
            files = tree["files"]
            files_with_counts = [
                (f, self.file_change_count.get(f, 0)) for f in files
            ]
            files_with_counts.sort(key=lambda x: x[1], reverse=True)

            if len(files_with_counts) > self.max_files_per_dir:
                tree["files"] = [f for f, _ in files_with_counts[: self.max_files_per_dir]]
                tree["truncated"] = len(files_with_counts) - self.max_files_per_dir
            else:
                tree["files"] = [f for f, _ in files_with_counts]

        if "dirs" in tree:
            for subdir in tree["dirs"].values():
                self._limit_files(subdir)

    def get_file_heat(self, file_name: str, parent_path: str = ""):
        """获取文件的热度值（修改次数）"""
        full_path = f"{parent_path}/{file_name}" if parent_path else file_name
        return self.file_change_count.get(full_path, 0)

    def calculate_figure_size(self, tree):
        """根据树的规模自适应计算 figure size"""
        # 预先计算总共需要多少行
        self.total_lines = 0
        self._count_lines(tree)

        # 根据行数计算高度，每行约 0.4 英寸
        height = max(self.total_lines * 0.4, 10)  # 最小 10 英寸
        width = 20  # 固定宽度

        print(f"📏 计算图表尺寸: {self.total_lines} 行 -> {width}x{height} 英寸")
        return (width, height)

    def _count_lines(self, tree):
        """递归统计需要显示的总行数"""
        # 每个目录占 0.8 行
        if "dirs" in tree:
            for subdir in tree["dirs"].values():
                self.total_lines += 1
                self._count_lines(subdir)

        # 每个文件占 0.5 行
        if "files" in tree:
            self.total_lines += len(tree["files"]) * 0.6

        # 截断提示占 0.5 行
        if "truncated" in tree and tree["truncated"] > 0:
            self.total_lines += 0.6

    def plot_tree(self, tree, output_path: str = "output/s1_repo_heatmap.png"):
        """绘制热力图树状图"""
        print("🎨 正在绘制热力图...")

        # 设置中文字体（如果可用）
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass

        # 计算 figure size
        fig_size = self.calculate_figure_size(tree)
        fig, ax = plt.subplots(figsize=fig_size, dpi=100)

        # 设置颜色映射（白色 -> 黄色 -> 红色）
        colors = ["#f0f0f0", "#fff7bc", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02", "#8c2d04"]
        n_bins = 100
        cmap = LinearSegmentedColormap.from_list("heat", colors, N=n_bins)

        # 获取最大修改次数用于归一化
        max_changes = max(self.file_change_count.values()) if self.file_change_count else 1

        # 绘制树
        y_pos = [0]  # 使用列表以便在递归中修改
        self._draw_node(ax, tree, x=0, y_pos=y_pos, cmap=cmap, max_changes=max_changes)

        # 设置图表
        ax.set_xlim(-0.5, 12)
        ax.set_ylim(y_pos[0] - 1, 1)
        ax.axis("off")
        ax.set_title(
            f"Git Repo Heatmap: {self.repo_path.name}\n"
            f"(max_depth={self.max_depth}, max_files_per_dir={self.max_files_per_dir})",
            fontsize=14,
            fontweight="bold",
            pad=20,
        )

        # 添加颜色条说明
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, max_changes))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, pad=0.01, fraction=0.03, aspect=30)
        cbar.set_label("Change Count", rotation=270, labelpad=20, fontsize=10)

        # 保存
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches="tight", dpi=150)
        print(f"✓ 图表已保存到: {output_path}")

        plt.close()

    def _draw_node(
        self, ax, tree, x, y_pos, parent_path="", cmap=None, max_changes=1, level=0
    ):
        """递归绘制树节点"""
        indent = 1.2

        # 绘制目录
        if "dirs" in tree:
            for dir_name, subtree in sorted(tree["dirs"].items()):
                y_pos[0] -= 0.8
                y = y_pos[0]

                # 绘制目录名
                ax.text(
                    x,
                    y,
                    f"[{dir_name}/]",
                    fontsize=9,
                    fontweight="bold",
                    va="center",
                    color="#2166ac",
                    family="monospace",
                )

                # 递归绘制子树
                new_path = f"{parent_path}/{dir_name}" if parent_path else dir_name
                self._draw_node(
                    ax,
                    subtree,
                    x + indent,
                    y_pos,
                    new_path,
                    cmap,
                    max_changes,
                    level + 1,
                )

        # 绘制文件
        if "files" in tree:
            for file_name in tree["files"]:
                y_pos[0] -= 0.5
                y = y_pos[0]

                # 获取热度值
                full_path = f"{parent_path}/{file_name}" if parent_path else file_name
                heat = self.file_change_count.get(full_path, 0)
                normalized_heat = heat / max_changes if max_changes > 0 else 0

                # 获取颜色
                color = cmap(normalized_heat)

                # 绘制文件（带背景色）
                bbox = dict(
                    boxstyle="round,pad=0.25",
                    facecolor=color,
                    edgecolor="#888888",
                    linewidth=0.5,
                    alpha=0.9
                )

                # 截断过长的文件名
                display_name = file_name if len(file_name) <= 40 else file_name[:37] + "..."

                ax.text(
                    x,
                    y,
                    f"{display_name} ({heat})",
                    fontsize=7,
                    va="center",
                    bbox=bbox,
                    family="monospace",
                )

        # 如果有被截断的文件，显示提示
        if "truncated" in tree and tree["truncated"] > 0:
            y_pos[0] -= 0.5
            y = y_pos[0]
            ax.text(
                x,
                y,
                f"... (+{tree['truncated']} more files)",
                fontsize=7,
                style="italic",
                color="#999999",
                family="monospace",
            )

    def run(self, output_path: str = "output/s1_repo_heatmap.png"):
        """运行完整流程"""
        print(f"🚀 开始分析仓库: {self.repo_path}")
        self.collect_file_changes()
        tree = self.build_tree_structure()
        self.plot_tree(tree, output_path)
        print("🎉 完成！")


def main():
    parser = argparse.ArgumentParser(description="生成 Git 仓库结构的热力图")
    parser.add_argument("repo_path", help="Git 仓库路径")
    parser.add_argument(
        "--max-depth", type=int, default=5, help="最大目录深度 (默认: 5)"
    )
    parser.add_argument(
        "--max-files", type=int, default=20, help="每个目录最多显示的文件数 (默认: 20)"
    )
    parser.add_argument(
        "--output", "-o", help="输出文件路径（默认：output/<repo_name>/s1_heatmap.png）"
    )

    args = parser.parse_args()

    # 获取仓库名称
    repo_name = Path(args.repo_path).name

    # 默认输出路径：output/<repo_name>/s1_heatmap.png
    if args.output is None:
        args.output = f"output/{repo_name}/s1_heatmap.png"

    heatmap = RepoTreeHeatmap(args.repo_path, args.max_depth, args.max_files)
    heatmap.run(args.output)


if __name__ == "__main__":
    main()
