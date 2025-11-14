# Understanding Everything

通过 Git 历史和 AI 分析，将代码仓库转换为通俗易懂的"武林秘籍"。

## 项目简介

这是一个用于深度理解代码仓库的工具链。它通过分析 Git 历史、使用 AI 解读代码、生成层级文档，最终创建一个交互式网站，让你能够轻松理解任何复杂的代码库。

## 核心功能

✅ **可视化分析**：生成仓库结构热力图，直观展示文件修改频率
✅ **智能统计**：分析代码规模、修改分布、Token 数量
✅ **AI 解读**：使用 Gemini 2.5 Pro 生成通俗易懂的代码解释
✅ **层级文档**：自底向上递归生成各层级 README
✅ **交互式网站**：Read the Docs 风格的静态网站，支持文件树导航

## 项目结构

```
understanding-everything/
├── scripts/              # 5 个核心脚本（按执行顺序命名）
│   ├── s1_repo_heatmap_tree.py    # 生成仓库结构热力图
│   ├── s2_analyze_stats.py        # 分析统计信息
│   ├── s3_explain_files.py        # AI 解读代码文件
│   ├── s4_generate_readme.py      # 生成层级 README
│   └── s5_website.py              # 生成交互式网站
├── repo/                 # 待分析的仓库（.gitignore 已忽略）
├── output/              # 生成的所有输出（.gitignore 已忽略）
│   └── <repo_name>/
│       ├── s1_heatmap.png        # 热力图
│       ├── explain/              # AI 解读的 markdown
│       └── website/              # 静态网站
└── pyproject.toml       # 项目配置
```

## 快速开始

### 1. 环境设置

```bash
# 创建虚拟环境
uvpp 3.12
sva
uvpe
```

### 2. 配置 API

设置环境变量（用于 Gemini API）：
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://openai.app.msh.team/v1"
```

### 3. 完整分析流程

假设要分析 `repo/mshrl` 仓库：

```bash
# Step 1: 生成热力图（可视化修改频率）
python scripts/s1_repo_heatmap_tree.py repo/mshrl

# Step 2: 分析统计信息（了解代码规模）
python scripts/s2_analyze_stats.py repo/mshrl --subdir mshrl

# Step 3: AI 解读文件（生成通俗解释）
python scripts/s3_explain_files.py repo/mshrl --subdir mshrl --percent 100

# Step 4: 生成层级 README（自底向上汇总）
python scripts/s4_generate_readme.py repo/mshrl --subdir mshrl

# Step 5: 生成交互式网站（最终产物）
python scripts/s5_website.py repo/mshrl --subdir mshrl
```

### 4. 查看结果

启动本地服务器查看网站：
```bash
cd output/mshrl/website
python -m http.server 8000
# 浏览器打开 http://localhost:8000
```

---

## 脚本详细说明

### S1 - 生成仓库结构热力图

**功能**：可视化展示仓库结构和文件修改频率

**特点**：
- 树状显示目录和文件
- 颜色编码：白色 → 黄色 → 橙色 → 红色（修改次数递增）
- 自适应图片大小
- 限制深度和文件数，避免过于复杂

**使用**：
```bash
python scripts/s1_repo_heatmap_tree.py <repo_path> [options]

# 示例
python scripts/s1_repo_heatmap_tree.py repo/mshrl \
  --max-depth 5 \
  --max-files 20 \
  -o output/custom_heatmap.png
```

**输出**：`output/<repo_name>/s1_heatmap.png`

---

### S2 - 分析统计信息

**功能**：统计代码规模、修改分布、Token 数量

**特点**：
- 使用 `tiktoken o200k_base` 精确计算 Token 数
- 显示修改次数的分位数分布（P50, P75, P90, P95, P99）
- 按百分比展示文件分层统计（1%, 5%, 10%, ...）
- 列出 Top 10 最频繁修改的文件

**使用**：
```bash
python scripts/s2_analyze_stats.py <repo_path> --subdir <subdir>

# 示例
python scripts/s2_analyze_stats.py repo/mshrl --subdir mshrl
```

**输出示例**：
```
📊 总体统计:
   - 总文件数: 85
   - 总 Token 数: 183,600 (~183.6K tokens)
   - 平均每文件: 2160 tokens

📊 修改次数分位数:
   - P50: 6 次
   - P90: 61 次
   - P99: 439 次
```

---

### S3 - AI 解读代码文件

**功能**：使用 Gemini 2.5 Pro 为每个文件生成通俗易懂的中文解释

**特点**：
- 支持 `--top N` 或 `--percent N` 选择要解读的文件
- 自动跳过已解读的文件
- 使用 `tqdm` 显示进度条
- Prompt 优化为"step-by-step 讲解"风格

**使用**：
```bash
python scripts/s3_explain_files.py <repo_path> --subdir <subdir> [options]

# 解读前 10 个文件
python scripts/s3_explain_files.py repo/mshrl --subdir mshrl --top 10

# 解读前 50% 的文件
python scripts/s3_explain_files.py repo/mshrl --subdir mshrl --percent 50

# 强制重新生成
python scripts/s3_explain_files.py repo/mshrl --subdir mshrl --percent 100 --force
```

**输出**：`output/<repo_name>/explain/<subdir>/*.md`

---

### S4 - 生成层级 README

**功能**：递归地为每个文件夹生成汇总 README（自底向上）

**特点**：
- 从最底层文件夹开始，逐层向上汇总
- 子文件夹用其 README 代表，文件用其解读代表
- 如果内容超过 200K tokens，等比例截断
- 使用通俗易懂的 Prompt 生成汇总

**使用**：
```bash
python scripts/s4_generate_readme.py <repo_path> --subdir <subdir> [options]

# 示例
python scripts/s4_generate_readme.py repo/mshrl --subdir mshrl

# 强制重新生成
python scripts/s4_generate_readme.py repo/mshrl --subdir mshrl --force
```

**输出**：在每个文件夹下生成 `README.md`

---

### S5 - 生成交互式网站

**功能**：生成 Read the Docs 风格的静态网站

**特点**：
- 左侧可折叠文件树导航
- 点击文件夹显示 README 汇总
- 点击文件显示 AI 解读 + 原始代码（带语法高亮）
- 使用 Prism.js 进行代码高亮
- 响应式设计，移动端友好

**使用**：
```bash
python scripts/s5_website.py <repo_path> --subdir <subdir> [options]

# 示例
python scripts/s5_website.py repo/mshrl --subdir mshrl
```

**输出**：
- `output/<repo_name>/website/index.html`
- `output/<repo_name>/website/styles.css`
- `output/<repo_name>/website/app.js`
- `output/<repo_name>/website/sources/` - 源代码
- `output/<repo_name>/website/explanations/` - 解读（HTML）

**查看网站**：
```bash
cd output/<repo_name>/website
python -m http.server 8000
```

---

## 技术栈

- **Python 3.12+**
- **GitPython** - Git 仓库操作
- **Matplotlib** - 热力图可视化
- **NumPy** - 数值计算
- **Tiktoken** - Token 计数
- **OpenAI SDK** - Gemini API 调用
- **Markdown** - Markdown → HTML 转换
- **Prism.js** - 代码语法高亮
- **TQDM** - 进度条显示

## 设计理念

1. **极简主义**：每个脚本专注一件事，代码简洁明了
2. **顺序清晰**：s1 → s2 → s3 → s4 → s5，按执行顺序命名
3. **可中断**：每一步都可独立运行，支持增量更新
4. **数据驱动**：基于真实项目（mshrl、Megatron-LM）验证

## 示例项目

已成功分析的项目：
- ✅ **mshrl** (85 files, 183.6K tokens) - 强化学习训练框架
- ✅ **Megatron-LM** (Top 10%, 17 files, 116.3K tokens) - 大规模语言模型训练

## 许可证

MIT License

## 致谢

- **Gemini 2.5 Pro** - 强大的代码理解能力
- **Claude Code** - 优秀的编程助手
