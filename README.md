<div align="center">

# Understand Everything

![Understand Everything Banner](assets/promotional-banner.png)

**Transform any code repository into easy-to-understand interactive documentation through Git history and AI analysis.**

[🌐 Project Website](https://mor-li.github.io/understand-everything/index.html) |
[⚡ flash-linear-attention Demo](https://mor-li.github.io/understand-everything/output/flash-linear-attention/index.html) |
[📖 verl Demo](https://mor-li.github.io/understand-everything/output/verl/index.html) |
[🔥 Megatron-LM Demo](https://mor-li.github.io/understand-everything/output/Megatron-LM/index.html) |
[🦙 LLaMA-Factory Demo](https://mor-li.github.io/understand-everything/output/LLaMA-Factory/index.html) |
[✏️ EasyEdit Demo](https://mor-li.github.io/understand-everything/output/EasyEdit/index.html)

English | [简体中文](assets/README_zh.md)

</div>

## Overview

A toolchain for deeply understanding code repositories. It analyzes Git history, uses AI to interpret code, generates hierarchical documentation, and creates an interactive website that helps you easily understand any complex codebase.

## Key Features

- **Visual Analysis**: Generate repository structure heatmaps showing file modification frequency
- **Smart Statistics**: Analyze code size, modification distribution, and token counts
- **AI Interpretation**: Use Gemini 3 Pro Preview to generate easy-to-understand code explanations
- **Hierarchical Docs**: Recursively generate README files for each directory (bottom-up)
- **Interactive Website**: Read the Docs style static website with file tree navigation

## Project Structure

```
understand-everything/
├── scripts/              # Core scripts (named by execution order)
│   ├── s0_find_snapshots.py       # Find curriculum learning snapshots
│   ├── s1_curriculum_pipeline.py  # Curriculum learning pipeline
│   ├── s2_explain_files.py        # AI interprets code files
│   ├── s3_generate_readme.py      # Generate hierarchical READMEs
│   └── s4_website.py              # Generate interactive website
├── utils/               # Utility scripts
│   ├── s0_add_timestamps.py       # Add timestamps
│   ├── s1_repo_heatmap_tree.py    # Generate repo structure heatmap
│   ├── s2_analyze_stats.py        # Analyze statistics
│   └── utils.py                   # Common utility functions
├── repo/                # Repositories to analyze (.gitignore ignored)
├── output/              # All generated output (.gitignore ignored)
│   └── <repo_name>/
│       ├── explain/              # AI interpretation markdown
│       └── website/              # Static website
└── pyproject.toml       # Project configuration
```

## Quick Start

### 1. Environment Setup

```bash
# Create virtual environment
uv venv --seed .venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

### 2. Configure API

Set environment variables (for Gemini API):
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="your-openai-base-url"
```

### 3. Complete Analysis Pipeline

Assuming you want to analyze `repo/your-project`:

```bash
# Step 1: AI interprets files (generates explanations)
python scripts/s2_explain_files.py repo/your-project --workers 8 --percent 100

# Step 2: Generate hierarchical READMEs (bottom-up summarization)
python scripts/s3_generate_readme.py repo/your-project

# Step 3: Generate interactive website (final output)
python scripts/s4_website.py repo/your-project
```

**Optional utility scripts**:

```bash
# Generate repo heatmap (visualize modification frequency)
python utils/s1_repo_heatmap_tree.py repo/your-project

# Analyze statistics (understand code scale)
python utils/s2_analyze_stats.py repo/your-project
```

### 4. View Results

Start a local server to view the website:
```bash
cd output/your-project/website-<date>
python -m http.server 8000
# Open http://localhost:8000 in browser
```

## Core Scripts

### S2 - AI Code Interpretation

**Function**: Use Gemini 3 Pro Preview to generate easy-to-understand explanations for each file

**Features**:
- Async concurrent processing, supports `--workers N` to set concurrency (default 16)
- Supports `--top N` or `--percent N` to select files to interpret
- Automatically skips already interpreted files (use `--force` to regenerate)
- Uses `tqdm` to show real-time progress bar
- Prompt optimized for "step-by-step explanation" style

**Usage**:
```bash
python scripts/s2_explain_files.py <repo_path> [options]

# Interpret all files with 8 workers
python scripts/s2_explain_files.py repo/your-project --workers 8 --percent 100

# Interpret top 50% of files
python scripts/s2_explain_files.py repo/your-project --percent 50

# Force regenerate
python scripts/s2_explain_files.py repo/your-project --percent 100 --force
```

**Output**: `output/<repo_name>/explain-<date>/*.md`

### S3 - Generate Hierarchical READMEs

**Function**: Recursively generate summary READMEs for each folder (bottom-up)

**Features**:
- Starts from deepest folders, summarizes layer by layer upward
- Subfolders represented by their READMEs, files by their interpretations
- If content exceeds 200K tokens, proportionally truncated
- Uses easy-to-understand prompts for summarization

**Usage**:
```bash
python scripts/s3_generate_readme.py <repo_path> [options]

# Example
python scripts/s3_generate_readme.py repo/your-project

# Force regenerate
python scripts/s3_generate_readme.py repo/your-project --force
```

**Output**: Generates `README.md` in each folder of the interpretation directory

### S4 - Generate Interactive Website

**Function**: Generate Read the Docs style static website

**Features**:
- Collapsible file tree navigation on the left, fixed indentation alignment
- Click folder to show README summary
- Click file to show AI interpretation + source code (with syntax highlighting)
- Supports all file types (.py, .cu, .cpp, .h, .md, etc.)
- Shows hidden files (except .git directory)
- Uses Prism.js for code highlighting
- Responsive design, mobile friendly

**Usage**:
```bash
python scripts/s4_website.py <repo_path> [options]

# Example
python scripts/s4_website.py repo/your-project
```

**Output**:
- `output/<repo_name>/website/index.html`
- `output/<repo_name>/website/styles.css`
- `output/<repo_name>/website/app.js`
- `output/<repo_name>/website/sources/` - Source code
- `output/<repo_name>/website/explanations/` - Interpretations (HTML)

## Demo Projects

Successfully analyzed open source projects:
- **[flash-linear-attention](https://github.com/fla-org/flash-linear-attention)** (468 files) - Triton implementation of efficient linear attention mechanisms
- **[verl](https://github.com/volcengine/verl)** (1100+ files) - ByteDance's large model reinforcement learning framework
- **[Megatron-LM](https://github.com/NVIDIA/Megatron-LM)** (1330+ files) - NVIDIA's large-scale Transformer training framework
- **[LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)** (405 files) - One-stop LLM fine-tuning framework supporting 100+ models
- **[EasyEdit](https://github.com/zjunlp/EasyEdit)** (834 files) - Knowledge editing framework with 28+ editing methods

## Tech Stack

- **Python 3.12+**
- **GitPython** - Git repository operations
- **Matplotlib** - Heatmap visualization
- **NumPy** - Numerical computation
- **Tiktoken** - Token counting
- **OpenAI SDK** - Gemini API calls
- **Markdown** - Markdown → HTML conversion
- **Prism.js** - Code syntax highlighting
- **TQDM** - Progress bar display

## Design Philosophy

1. **Minimalism**: Each script focuses on one thing, code is clean and clear
2. **Clear Order**: s1 → s2 → s3, named by execution order
3. **Interruptible**: Each step runs independently, supports incremental updates
4. **Concurrent & Efficient**: Async processing, supports multiple workers

## License

MIT License

## Acknowledgments

- **Gemini 3 Pro Preview** - Powerful code understanding capabilities
- **Claude Code** - Excellent programming assistant
