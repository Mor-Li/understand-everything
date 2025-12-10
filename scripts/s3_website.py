"""
s5_website.py
生成 Read the Docs 风格的静态网站，展示代码解读和层级结构
"""

import argparse
import json
from pathlib import Path
from typing import Any

import markdown
import sys

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.utils import get_output_path


def sanitize_dotfile_path(path: Path) -> Path:
    """
    将路径中以 . 开头的目录/文件名改为 _ 开头
    GitHub Pages 不提供 .github 等 dotfile 目录的静态文件

    Args:
        path: 原始路径

    Returns:
        处理后的路径
    """
    parts = []
    for part in path.parts:
        if part.startswith('.') and part != '.' and part != '..':
            parts.append('_' + part[1:])  # .github -> _github
        else:
            parts.append(part)
    return Path(*parts) if parts else path


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
        # 根目录使用仓库名称，避免和子目录同名造成混淆
        is_root = current_path == repo_folder
        display_name = repo_path.name if is_root else current_path.name

        node = {
            "name": display_name,
            "type": "folder",
            "path": str(current_path.relative_to(repo_path)),
            "children": []
        }

        # 检查是否有 README.md
        readme_path = current_explain / "README.md"
        if readme_path.exists():
            # 对路径进行 dotfile 处理（.github -> _github）
            sanitized_readme = sanitize_dotfile_path(readme_path.relative_to(explain_base))
            node["readme"] = str(sanitized_readme)

        # 收集子文件夹
        folders = []
        files = []

        if current_path.exists():
            for item in sorted(current_path.iterdir()):
                # Skip .git directory only (not source code)
                if item.name == ".git":
                    continue

                if item.is_dir():
                    folders.append(item)
                elif item.is_file():
                    files.append(item)

        # 递归处理子文件夹
        for folder in folders:
            sub_explain = current_explain / folder.name
            node["children"].append(build_node(folder, sub_explain))

        # 处理文件
        for file in files:
            # 对路径进行 dotfile 处理（.github -> _github）
            sanitized_source = sanitize_dotfile_path(file.relative_to(repo_path))
            file_node = {
                "name": file.name,
                "type": "file",
                "path": str(file.relative_to(repo_path)),
                "source": str(sanitized_source)
            }

            # 检查是否有对应的解读 .md 文件
            # 所有文件的解读都是 filename.ext.md（包括 .md 文件变成 filename.md.md）
            explain_md = current_explain / (file.name + ".md")
            if explain_md.exists():
                # 对路径进行 dotfile 处理（.github -> _github）
                sanitized_explain = sanitize_dotfile_path(explain_md.relative_to(explain_base))
                file_node["explanation"] = str(sanitized_explain)

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

    # 收集所有需要复制的文件（包括根目录的文件）
    all_files = []

    # 先添加根目录的文件
    if source_folder.exists():
        for item in source_folder.iterdir():
            if item.name == ".git":
                continue
            if item.is_file():
                all_files.append(item)

    # 再添加子目录中的文件
    for source_file in source_folder.rglob("*"):
        if not source_file.is_file():
            continue
        if ".git" in str(source_file):
            continue
        all_files.append(source_file)

    # 复制所有文件
    for source_file in all_files:
        rel_path = source_file.relative_to(source_folder)
        # 对路径进行 dotfile 处理（.github -> _github）
        sanitized_rel_path = sanitize_dotfile_path(rel_path)
        dest_file = output_source / sanitized_rel_path

        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # 尝试作为文本文件复制，如果失败则作为二进制文件复制
        try:
            dest_file.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")
        except (UnicodeDecodeError, UnicodeError):
            dest_file.write_bytes(source_file.read_bytes())

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
        # 对路径进行 dotfile 处理（.github -> _github）
        sanitized_rel_path = sanitize_dotfile_path(rel_path)
        dest_file = output_explain / sanitized_rel_path

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
    overflow-x: auto;
    padding: 10px;
    min-width: 0;
}

/* 文件树样式 */
.tree-node {
    margin: 2px 0;
}

.tree-label {
    display: flex;
    align-items: center;
    padding: 6px 8px;
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
    margin-right: 6px;
    font-size: 1em;
    flex-shrink: 0;
}

.tree-toggle {
    margin-right: 4px;
    font-size: 0.75em;
    width: 14px;
    text-align: center;
    flex-shrink: 0;
}

.tree-name {
    white-space: nowrap;
}

.tree-children {
    margin-left: 0;
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
    // Apply margin to the entire node instead of padding to label
    div.style.marginLeft = `${level * 20}px`;

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
    name.className = 'tree-name';
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
            <div class="markdown-content">
                <p style="color: #666; padding: 20px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #3498db;">
                    欢迎查看代码解读！请从左侧导航栏选择文件或文件夹。
                </p>
            </div>
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
                <div class="markdown-content">
                    <p style="color: #666; padding: 20px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #e67e22;">
                        该文件夹暂无说明文档。
                    </p>
                </div>
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
        // Convert .md to .html
        let htmlPath = readmePath;
        if (htmlPath.endsWith('.md')) {
            htmlPath = htmlPath.slice(0, -3) + '.html';
        }
        // Encode path components to handle special characters and dots
        const encodedPath = htmlPath.split('/').map(encodeURIComponent).join('/');
        const response = await fetch(`explanations/${encodedPath}`);

        // Check if fetch was successful
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

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
        // Show consistent error message with same layout as normal content
        document.getElementById('content-area').innerHTML = `
            <div class="content-header">
                <h1>📁 ${folderName}</h1>
            </div>
            <div class="markdown-content">
                <p style="color: #666; padding: 20px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #e67e22;">
                    该文件夹暂无说明文档。
                </p>
            </div>
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
            // Convert .md to .html, handling both regular files (.ext.md -> .ext.html)
            // and markdown files (.md -> .html)
            let htmlPath = node.explanation;
            if (htmlPath.endsWith('.md')) {
                htmlPath = htmlPath.slice(0, -3) + '.html';
            }
            // Encode path components to handle special characters and dots
            const encodedPath = htmlPath.split('/').map(encodeURIComponent).join('/');
            const response = await fetch(`explanations/${encodedPath}`);
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
            // Encode path components to handle special characters and dots
            const encodedSource = node.source.split('/').map(encodeURIComponent).join('/');
            const sourceResponse = await fetch(`sources/${encodedSource}`);
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
                <h1>📄 ${node.name}</h1>
                <p style="color: #666; margin-top: 10px;">${node.path}</p>
            </div>
            <div class="markdown-content">
                <p style="color: #666; padding: 20px; background: #fff5f5; border-radius: 5px; border-left: 4px solid #e74c3c;">
                    加载失败：${error.message}
                </p>
            </div>
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
    parser.add_argument("--subdir", default="", help="要分析的子目录（默认为空，分析整个仓库）")
    parser.add_argument("--explain", help="explain 输出目录（默认：output/<repo_name>/explain）")
    parser.add_argument("--output", "-o", help="网站输出目录（默认：output/<repo_name>/website）")

    args = parser.parse_args()

    repo_path = Path(args.repo_path)
    subdir = Path(args.subdir) if args.subdir else Path(".")
    repo_name = repo_path.name

    # 默认路径
    if args.explain is None:
        args.explain = get_output_path(args.repo_path, args.subdir, "explain")
    if args.output is None:
        args.output = get_output_path(args.repo_path, args.subdir, "website")

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
