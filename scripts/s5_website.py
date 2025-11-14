"""
s5_website.py
生成 Read the Docs 风格的静态网站，展示代码解读和层级结构
"""

import argparse
import json
from pathlib import Path
from typing import Any

import markdown


def build_tree_structure(repo_path: Path, subdir: Path, explain_base: Path) -> dict[str, Any]:
    """
    构建文件树结构

    Args:
        repo_path: 仓库路径
        subdir: 子目录（相对于仓库根目录）
        explain_base: explain 输出的基础路径

    Returns:
        树状结构字典
    """
    repo_folder = repo_path / subdir
    explain_folder = explain_base / subdir

    def build_node(current_path: Path, current_explain: Path) -> dict[str, Any]:
        """递归构建节点"""
        node = {
            "name": current_path.name,
            "type": "folder",
            "path": str(current_path.relative_to(repo_path)),
            "children": []
        }

        # 检查是否有 README.md
        readme_path = current_explain / "README.md"
        if readme_path.exists():
            node["readme"] = str(readme_path.relative_to(explain_base))

        # 收集子文件夹
        folders = []
        files = []

        if current_path.exists():
            for item in sorted(current_path.iterdir()):
                if item.name.startswith("."):
                    continue

                if item.is_dir():
                    folders.append(item)
                elif item.is_file() and item.suffix == ".py":
                    files.append(item)

        # 递归处理子文件夹
        for folder in folders:
            sub_explain = current_explain / folder.name
            node["children"].append(build_node(folder, sub_explain))

        # 处理文件
        for file in files:
            file_node = {
                "name": file.name,
                "type": "file",
                "path": str(file.relative_to(repo_path)),
                "source": str(file.relative_to(repo_path))
            }

            # 检查是否有对应的解读 .md 文件
            explain_md = current_explain / (file.name + ".md")
            if explain_md.exists():
                file_node["explanation"] = str(explain_md.relative_to(explain_base))

            node["children"].append(file_node)

        return node

    return build_node(repo_folder, explain_folder)


def copy_source_files(repo_path: Path, subdir: Path, output_dir: Path):
    """
    复制源代码文件到输出目录

    Args:
        repo_path: 仓库路径
        subdir: 子目录
        output_dir: 输出目录
    """
    source_folder = repo_path / subdir
    output_source = output_dir / "sources" / subdir

    print(f"📦 复制源代码文件...")

    for py_file in source_folder.rglob("*.py"):
        if ".git" in str(py_file):
            continue

        rel_path = py_file.relative_to(source_folder)
        dest_file = output_source / rel_path

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(py_file.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"✓ 源代码已复制到 {output_source}")


def copy_explanation_files(explain_base: Path, subdir: Path, output_dir: Path):
    """
    复制解读 markdown 文件到输出目录

    Args:
        explain_base: explain 输出的基础路径
        subdir: 子目录
        output_dir: 输出目录
    """
    explain_folder = explain_base / subdir
    output_explain = output_dir / "explanations" / subdir

    print(f"📝 复制解读文件...")

    for md_file in explain_folder.rglob("*.md"):
        rel_path = md_file.relative_to(explain_folder)
        dest_file = output_explain / rel_path

        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # 将 markdown 转换为 HTML
        md_content = md_file.read_text(encoding="utf-8")
        html_content = markdown.markdown(
            md_content,
            extensions=["fenced_code", "tables", "codehilite"]
        )

        dest_file.with_suffix(".html").write_text(html_content, encoding="utf-8")

    print(f"✓ 解读文件已复制到 {output_explain}")


def generate_index_html(output_dir: Path, tree: dict[str, Any], repo_name: str):
    """
    生成主 index.html

    Args:
        output_dir: 输出目录
        tree: 文件树结构
        repo_name: 仓库名称
    """
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{repo_name} - 代码解读</title>
    <link rel="stylesheet" href="styles.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
</head>
<body>
    <div class="container">
        <!-- 左侧导航栏 -->
        <nav class="sidebar">
            <div class="sidebar-header">
                <h2>{repo_name}</h2>
            </div>
            <div class="tree-container" id="tree-container"></div>
        </nav>

        <!-- 右侧内容区 -->
        <main class="content">
            <div id="content-area">
                <div class="loading">加载中...</div>
            </div>
        </main>
    </div>

    <script>
        // 文件树数据
        const treeData = {json.dumps(tree, ensure_ascii=False, indent=2)};
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-bash.min.js"></script>
    <script src="app.js"></script>
</body>
</html>"""

    index_file = output_dir / "index.html"
    index_file.write_text(html_content, encoding="utf-8")
    print(f"✓ 已生成 {index_file}")


def generate_css(output_dir: Path):
    """生成 CSS 样式文件"""
    css_content = """/* 全局样式 */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    background: #f5f5f5;
}

/* 容器布局 */
.container {
    display: flex;
    height: 100vh;
    overflow: hidden;
}

/* 左侧导航栏 */
.sidebar {
    width: 320px;
    background: #2c3e50;
    color: #ecf0f1;
    display: flex;
    flex-direction: column;
    box-shadow: 2px 0 5px rgba(0, 0, 0, 0.1);
}

.sidebar-header {
    padding: 20px;
    background: #1a252f;
    border-bottom: 1px solid #34495e;
}

.sidebar-header h2 {
    font-size: 1.4em;
    font-weight: 600;
}

.tree-container {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
}

/* 文件树样式 */
.tree-node {
    margin: 2px 0;
}

.tree-label {
    display: flex;
    align-items: center;
    padding: 8px 10px;
    cursor: pointer;
    border-radius: 4px;
    transition: background 0.2s;
    user-select: none;
}

.tree-label:hover {
    background: #34495e;
}

.tree-label.active {
    background: #3498db;
    font-weight: 600;
}

.tree-icon {
    margin-right: 8px;
    font-size: 1.1em;
}

.tree-toggle {
    margin-right: 5px;
    font-size: 0.8em;
    width: 16px;
    text-align: center;
}

.tree-children {
    margin-left: 20px;
    display: none;
}

.tree-children.expanded {
    display: block;
}

/* 右侧内容区 */
.content {
    flex: 1;
    background: #fff;
    overflow-y: auto;
    padding: 40px;
}

.loading {
    text-align: center;
    padding: 40px;
    color: #999;
}

/* 内容样式 */
.content-header {
    border-bottom: 2px solid #3498db;
    padding-bottom: 15px;
    margin-bottom: 30px;
}

.content-header h1 {
    font-size: 2em;
    color: #2c3e50;
}

.content-section {
    margin-bottom: 40px;
}

.content-section h2 {
    font-size: 1.5em;
    color: #2c3e50;
    margin-bottom: 15px;
    border-left: 4px solid #3498db;
    padding-left: 15px;
}

.content-section h3 {
    font-size: 1.2em;
    color: #34495e;
    margin: 20px 0 10px 0;
}

/* 代码块样式 */
pre {
    background: #2d2d2d;
    border-radius: 5px;
    padding: 20px;
    overflow-x: auto;
    margin: 15px 0;
}

pre code {
    font-family: "Fira Code", "Consolas", "Monaco", monospace;
    font-size: 0.9em;
    line-height: 1.5;
}

/* Markdown 内容样式 */
.markdown-content {
    line-height: 1.8;
}

.markdown-content p {
    margin: 15px 0;
}

.markdown-content ul, .markdown-content ol {
    margin: 15px 0;
    padding-left: 30px;
}

.markdown-content li {
    margin: 8px 0;
}

.markdown-content blockquote {
    border-left: 4px solid #3498db;
    padding-left: 20px;
    margin: 20px 0;
    color: #666;
    font-style: italic;
}

/* Markdown 中的代码块样式 - 确保文字可见 */
.markdown-content pre {
    background: #2d2d2d;
    border-radius: 5px;
    padding: 20px;
    overflow-x: auto;
    margin: 15px 0;
}

.markdown-content pre code {
    font-family: "Fira Code", "Consolas", "Monaco", monospace;
    font-size: 0.9em;
    line-height: 1.5;
    color: #ccc !important;
}

/* codehilite 扩展生成的代码块 */
.markdown-content .codehilite {
    background: #2d2d2d;
    border-radius: 5px;
    margin: 15px 0;
}

.markdown-content .codehilite pre {
    background: transparent;
    margin: 0;
    padding: 20px;
}

/* codehilite 中的所有 span 元素（语法高亮） */
.markdown-content .codehilite pre span {
    color: #ccc;
}

/* Markdown 中的行内代码 */
.markdown-content code {
    background: #f4f4f4;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Fira Code", "Consolas", "Monaco", monospace;
    font-size: 0.9em;
    color: #e74c3c;
}

/* 但是 pre 里的 code 不应该有行内代码的样式 */
.markdown-content pre code {
    background: transparent;
    padding: 0;
    border-radius: 0;
    color: #ccc !important;
}

/* 滚动条样式 */
::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
    background: #555;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .sidebar {
        width: 250px;
    }

    .content {
        padding: 20px;
    }
}"""

    css_file = output_dir / "styles.css"
    css_file.write_text(css_content, encoding="utf-8")
    print(f"✓ 已生成 {css_file}")


def generate_js(output_dir: Path):
    """生成 JavaScript 文件"""
    js_content = """// 应用状态
let currentPath = null;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    renderTree(treeData);
    loadDefaultContent();
});

// 渲染文件树
function renderTree(node) {
    const container = document.getElementById('tree-container');
    container.innerHTML = '';
    container.appendChild(renderNode(node));
}

// 渲染单个节点
function renderNode(node, level = 0) {
    const div = document.createElement('div');
    div.className = 'tree-node';

    const label = document.createElement('div');
    label.className = 'tree-label';

    // 切换图标
    if (node.type === 'folder' && node.children && node.children.length > 0) {
        const toggle = document.createElement('span');
        toggle.className = 'tree-toggle';
        toggle.textContent = '▶';
        label.appendChild(toggle);
    } else {
        const spacer = document.createElement('span');
        spacer.className = 'tree-toggle';
        spacer.textContent = ' ';
        label.appendChild(spacer);
    }

    // 文件/文件夹图标
    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = node.type === 'folder' ? '📁' : '📄';
    label.appendChild(icon);

    // 名称
    const name = document.createElement('span');
    name.textContent = node.name;
    label.appendChild(name);

    // 点击事件
    label.addEventListener('click', (e) => {
        e.stopPropagation();

        // 处理文件夹折叠/展开
        if (node.type === 'folder' && node.children && node.children.length > 0) {
            const children = div.querySelector('.tree-children');
            const toggle = label.querySelector('.tree-toggle');
            if (children.classList.contains('expanded')) {
                children.classList.remove('expanded');
                toggle.textContent = '▶';
            } else {
                children.classList.add('expanded');
                toggle.textContent = '▼';
            }
        }

        // 加载内容
        loadContent(node);

        // 更新激活状态
        document.querySelectorAll('.tree-label').forEach(el => el.classList.remove('active'));
        label.classList.add('active');
    });

    div.appendChild(label);

    // 递归渲染子节点
    if (node.children && node.children.length > 0) {
        const children = document.createElement('div');
        children.className = 'tree-children';

        node.children.forEach(child => {
            children.appendChild(renderNode(child, level + 1));
        });

        div.appendChild(children);
    }

    return div;
}

// 加载默认内容（顶层 README）
function loadDefaultContent() {
    if (treeData.readme) {
        loadReadme(treeData.readme, treeData.name);
    } else {
        document.getElementById('content-area').innerHTML = `
            <div class="content-header">
                <h1>${treeData.name}</h1>
            </div>
            <p>欢迎查看代码解读！请从左侧导航栏选择文件或文件夹。</p>
        `;
    }
}

// 加载内容
function loadContent(node) {
    currentPath = node.path;

    if (node.type === 'folder') {
        // 加载文件夹的 README
        if (node.readme) {
            loadReadme(node.readme, node.name);
        } else {
            document.getElementById('content-area').innerHTML = `
                <div class="content-header">
                    <h1>📁 ${node.name}</h1>
                </div>
                <p>该文件夹暂无说明文档。</p>
            `;
        }
    } else {
        // 加载文件的解读和源代码
        loadFile(node);
    }
}

// 加载 README
async function loadReadme(readmePath, folderName) {
    try {
        const htmlPath = readmePath.replace('.md', '.html');
        const response = await fetch(`explanations/${htmlPath}`);
        const html = await response.text();

        document.getElementById('content-area').innerHTML = `
            <div class="content-header">
                <h1>📁 ${folderName}</h1>
            </div>
            <div class="markdown-content">
                ${html}
            </div>
        `;
    } catch (error) {
        document.getElementById('content-area').innerHTML = `
            <div class="content-header">
                <h1>📁 ${folderName}</h1>
            </div>
            <p>加载失败：${error.message}</p>
        `;
    }
}

// 加载文件
async function loadFile(node) {
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = '<div class="loading">加载中...</div>';

    try {
        let html = `
            <div class="content-header">
                <h1>📄 ${node.name}</h1>
                <p style="color: #666; margin-top: 10px;">${node.path}</p>
            </div>
        `;

        // 加载解读
        if (node.explanation) {
            const htmlPath = node.explanation.replace('.md', '.html');
            const response = await fetch(`explanations/${htmlPath}`);
            const explanationHtml = await response.text();

            html += `
                <div class="content-section">
                    <h2>📖 AI 解读</h2>
                    <div class="markdown-content">
                        ${explanationHtml}
                    </div>
                </div>
            `;
        }

        // 加载源代码
        if (node.source) {
            const sourceResponse = await fetch(`sources/${node.source}`);
            const sourceCode = await sourceResponse.text();

            html += `
                <div class="content-section">
                    <h2>💻 源代码</h2>
                    <pre><code class="language-python">${escapeHtml(sourceCode)}</code></pre>
                </div>
            `;
        }

        contentArea.innerHTML = html;

        // 重新应用 Prism 语法高亮
        Prism.highlightAll();
    } catch (error) {
        contentArea.innerHTML = `
            <div class="content-header">
                <h1>❌ 加载失败</h1>
            </div>
            <p>${error.message}</p>
        `;
    }
}

// 转义 HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}"""

    js_file = output_dir / "app.js"
    js_file.write_text(js_content, encoding="utf-8")
    print(f"✓ 已生成 {js_file}")


def main():
    parser = argparse.ArgumentParser(description="生成代码解读静态网站")
    parser.add_argument("repo_path", help="Git 仓库路径")
    parser.add_argument("--subdir", default="mshrl", help="要分析的子目录")
    parser.add_argument("--explain", help="explain 输出目录（默认：output/<repo_name>/explain）")
    parser.add_argument("--output", "-o", help="网站输出目录（默认：output/<repo_name>/website）")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)
    repo_name = repo_path.name
    subdir = Path(args.subdir)

    # 默认路径
    if args.explain is None:
        args.explain = f"output/{repo_name}/explain"
    if args.output is None:
        args.output = f"output/{repo_name}/website"

    explain_base = Path(args.explain)
    output_dir = Path(args.output)

    print(f"🚀 开始生成网站: {repo_name}")
    print()

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建文件树
    print("🌲 构建文件树结构...")
    tree = build_tree_structure(repo_path, subdir, explain_base)
    print("✓ 文件树构建完成")
    print()

    # 复制源代码文件
    copy_source_files(repo_path, subdir, output_dir)
    print()

    # 复制解读文件
    copy_explanation_files(explain_base, subdir, output_dir)
    print()

    # 生成 HTML/CSS/JS
    print("🎨 生成网站文件...")
    generate_index_html(output_dir, tree, repo_name)
    generate_css(output_dir)
    generate_js(output_dir)
    print()

    print(f"🎉 完成！网站已生成到: {output_dir}")
    print(f"   打开 {output_dir}/index.html 即可查看")


if __name__ == "__main__":
    main()
