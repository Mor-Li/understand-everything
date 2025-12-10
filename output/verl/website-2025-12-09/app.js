// 应用状态
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
        const htmlPath = readmePath.replace('.md', '.html');
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
            const htmlPath = node.explanation.replace('.md', '.html');
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
}