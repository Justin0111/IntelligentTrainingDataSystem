# 配置说明

本文档详细介绍系统的所有配置选项。

## 环境变量配置

配置可通过 `.env` 文件或环境变量设置。

### LLM API 配置（必需）

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_PROVIDER` | `qwen` | LLM 服务提供商 |
| `LLM_API_KEY` | - | DashScope API 密钥（**必需**） |
| `LLM_MODEL_NAME` | `qwen-plus` | 使用的模型名称 |

**示例：**

```bash
LLM_PROVIDER=qwen
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_MODEL_NAME=qwen-plus
```

**可用模型：**
- `qwen-max` - 最强模型，效果最好
- `qwen-plus` - 平衡模型（推荐）
- `qwen-turbo` - 快速模型，成本最低

### GitHub 配置（可选）

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GITHUB_TOKEN` | - | GitHub Personal Access Token |

**作用：** 提高 GitHub API 请求限额（60/小时 → 5000/小时）

**获取方式：**
1. 访问 https://github.com/settings/tokens
2. 创建新 Token，权限只需勾选 `public_repo`

### 生成器配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GENERATOR_QA_PER_FILE` | `3` | 每个文件生成的问答对数量 |
| `GENERATOR_TIMEOUT` | `300` | 生成器超时时间（秒） |
| `GENERATOR_MAX_RETRIES` | `3` | 最大重试次数 |

### 处理器配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PROCESSOR_OUTPUT_FORMAT` | `alpaca` | 输出格式 |
| `PROCESSOR_AUTO_VALIDATE` | `true` | 是否自动验证数据 |
| `PROCESSOR_AUTO_CLEAN` | `true` | 是否自动清洗数据 |

**可用输出格式：**
- `jsonl` - JSON Lines 格式
- `json` - JSON 数组格式
- `alpaca` - Alpaca 训练格式
- `sharegpt` - ShareGPT 对话格式

### 日志配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_FILE` | `logs/system.log` | 日志文件路径 |

**日志级别：** `DEBUG`, `INFO`, `WARNING`, `ERROR`

### 目录配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `OUTPUT_DIR` | `output` | 数据输出目录 |
| `CACHE_DIR` | `.cache` | 缓存目录 |
| `TEMP_DIR` | `/tmp/training_data_gen` | 临时文件目录 |

## 配置文件示例

### 完整配置示例 (.env)

```bash
# ============================================
# LLM API 配置 (必需)
# ============================================
LLM_PROVIDER=qwen
LLM_API_KEY=your_dashscope_api_key_here
LLM_MODEL_NAME=qwen-plus

# ============================================
# GitHub 配置 (可选但推荐)
# ============================================
GITHUB_TOKEN=your_github_token_here

# ============================================
# 生成器配置 (可选)
# ============================================
GENERATOR_QA_PER_FILE=3
GENERATOR_TIMEOUT=300
GENERATOR_MAX_RETRIES=3

# ============================================
# 处理器配置 (可选)
# ============================================
PROCESSOR_OUTPUT_FORMAT=alpaca
PROCESSOR_AUTO_VALIDATE=true
PROCESSOR_AUTO_CLEAN=true

# ============================================
# 日志配置 (可选)
# ============================================
LOG_LEVEL=INFO
LOG_FILE=logs/system.log

# ============================================
# 目录配置 (可选)
# ============================================
OUTPUT_DIR=output
CACHE_DIR=.cache
```

### 最小配置

只需设置 API 密钥即可运行：

```bash
LLM_API_KEY=your_dashscope_api_key_here
```

## CLI 参数配置

除了环境变量，也可通过 CLI 参数覆盖配置：

```bash
python main.py generate-qa /path/to/repo \
    --output output/my_data \     # 输出目录
    --max-files 50 \              # 最大文件数
    --format alpaca \             # 输出格式
    --split                       # 划分数据集
```

## 配置优先级

1. **CLI 参数** - 最高优先级
2. **环境变量** - 中等优先级
3. **.env 文件** - 最低优先级
4. **默认值** - 兜底

## 相关文档

- [安装部署](installation.md)


