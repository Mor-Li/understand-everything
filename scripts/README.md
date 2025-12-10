# 代码仓库分析脚本

这个脚本工具链可以帮助你分析代码仓库，生成可视化的代码解读。

## 脚本列表

### s0_add_timestamps.py
给现有的 output 目录添加 git commit 时间戳。

**用途**: 用于迁移旧的 output 目录结构到带时间戳的新格式。

```bash
# 预览操作
python scripts/s0_add_timestamps.py --dry-run

# 执行重命名
python scripts/s0_add_timestamps.py
```

### s1_repo_heatmap_tree.py
生成仓库结构的热力图树状图。

**特点**:
- 最大深度：5 层
- 每个目录最多显示：20 个文件
- 颜色：根据 git 历史中文件被修改的频率（越红 = 修改越频繁）

```bash
python scripts/s1_repo_heatmap_tree.py repo/Megatron-LM \
    --max-depth 5 \
    --max-files 20
```

**输出**: `output/<repo_name>/s1_heatmap.png`

### s2_analyze_stats.py
分析指定子目录下文件的 git 修改统计信息。

```bash
python scripts/s2_analyze_stats.py repo/verl --subdir verl
```

**输出**: 打印统计信息到控制台，包括：
- 总体统计（文件数、token 数）
- 修改次数分布
- 按修改频率分层统计
- Top 10 最常修改的文件

### s3_explain_files.py
使用 Gemini API 对代码文件进行通俗易懂的解释（异步版本）。

**核心特性**：
- 异步并发处理，大幅提升速度（默认 16 个并发）
- 智能选择修改最频繁的文件进行解释
- 支持增量生成，避免重复消耗 API

```bash
# 解释 top 5 个文件（默认）
python scripts/s3_explain_files.py repo/verl --subdir verl

# 解释 top N 个文件
python scripts/s3_explain_files.py repo/verl --subdir verl --top 10

# 解释前 N% 的文件（按修改次数排序）
python scripts/s3_explain_files.py repo/verl --subdir verl --percent 20

# 自定义并发数（默认 16）
python scripts/s3_explain_files.py repo/verl --subdir verl --workers 32

# 强制重新生成
python scripts/s3_explain_files.py repo/verl --subdir verl --force

# 使用不同模型
python scripts/s3_explain_files.py repo/verl --subdir verl --model gemini-2.5-flash
```

**输出**: `output/<repo_name>/explain-<date>/<file_path>.md`

**环境变量**:
- `OPENAI_API_KEY`: API 密钥
- `OPENAI_BASE_URL`: API 基础 URL（可选）

**性能提升**：
- 串行版本：5 个文件约 25-150 秒（每个文件 5-30 秒）
- 异步版本：5 个文件约 5-30 秒（16 个并发同时处理）
- **速度提升：最高可达 16 倍**（取决于 API 响应时间）

### s4_generate_readme.py
递归生成各层级目录的 README.md（自底向上）。

```bash
# 生成 README
python scripts/s4_generate_readme.py repo/verl --subdir verl

# 强制重新生成
python scripts/s4_generate_readme.py repo/verl --subdir verl --force
```

**输出**: `output/<repo_name>/explain-<date>/<path>/README.md`

**特点**:
- 自动截断超长内容以满足 200K token 限制
- 自底向上生成，确保子目录的 README 先生成

### s5_website.py
生成 Read the Docs 风格的静态网站，展示代码解读和层级结构。

```bash
python scripts/s5_website.py repo/verl --subdir verl
```

**输出**: `output/<repo_name>/website-<date>/`

**功能**:
- 交互式文件树导航
- Markdown 渲染
- 响应式设计
- 代码高亮

## 工具函数 (utils.py)

提供通用的工具函数：

- `get_commit_date(repo_path)`: 获取仓库最新 commit 的日期
- `get_output_path(repo_path, subdir, output_type)`: 生成带时间戳的 output 路径
- `get_output_base(repo_path)`: 获取 output 基础路径（不含时间戳）

## Output 目录结构

```
output/
├── Megatron-LM/
│   ├── explain-2025-03-20/      # 代码解读（带 git commit 日期）
│   ├── website-2025-03-20/      # 静态网站（带 git commit 日期）
│   └── s1_heatmap.png          # 热力图
└── verl/
    ├── explain-2025-12-06/
    ├── website-2025-12-06/
    └── s1_verl_fixed.png
```

**时间戳说明**:
- 时间戳格式：`YYYY-MM-DD`
- 时间戳对应仓库最新 commit 的日期
- 这样可以区分不同版本代码的解读

## 完整工作流

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 生成热力图（可选）
python scripts/s1_repo_heatmap_tree.py repo/verl

# 3. 查看统计信息（可选）
python scripts/s2_analyze_stats.py repo/verl --subdir verl

# 4. 解释代码文件
python scripts/s3_explain_files.py repo/verl --subdir verl --percent 20

# 5. 生成层级 README
python scripts/s4_generate_readme.py repo/verl --subdir verl

# 6. 生成静态网站
python scripts/s5_website.py repo/verl --subdir verl

# 7. 预览网站
cd output/verl/website-2025-12-06
python -m http.server 8000
# 访问 http://localhost:8000
```

## 注意事项

1. **API 限制**: s3 和 s4 脚本需要调用 Gemini API，注意：
   - 设置好环境变量 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`
   - 注意 API 调用频率限制
   - token 使用量

2. **Token 计算**: 使用 `tiktoken o200k_base` 编码计算 token 数量

3. **时间戳**: 所有 output 目录都会自动添加 git commit 日期时间戳

4. **重复运行**: 使用 `--force` 参数强制重新生成已存在的文件
