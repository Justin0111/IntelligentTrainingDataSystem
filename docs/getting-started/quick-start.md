# 快速开始

5 分钟上手智能训练数据生成系统。

## 前置条件

- 已完成 [安装部署](installation.md)
- 已配置 LLM API 密钥（.env 文件）

## 三步快速上手

### 步骤 1: 分析代码仓库

```bash
python main.py analyze /path/to/your/repo
```

此命令会显示代码仓库的结构信息，包括：
- 文件总数和语言分布
- 类和函数数量
- 识别到的架构模式
- 依赖关系

### 步骤 2: 生成问答对数据

```bash
python main.py generate-qa /path/to/your/repo -o output/datasets --format alpaca
```

此命令会：
1. 扫描并解析代码仓库
2. 分析业务逻辑和规则
3. 调用 LLM 生成问答对
4. 验证和清洗数据
5. 输出到指定目录

### 步骤 3: 查看结果

```bash
# 查看生成的数据
head output/datasets/qa_dataset.alpaca

# 查看数据集说明
cat output/datasets/README.md
```

## 完整示例

### 示例 1: 单仓库处理

```bash
# 1. 激活环境
source venv/bin/activate

# 2. 设置 API Key（如果未配置 .env）
export DASHSCOPE_API_KEY='your-api-key'

# 3. 分析仓库
python main.py analyze /path/to/your/repo

# 4. 生成问答对（限制文件数以加快速度）
python main.py generate-qa /path/to/your/repo \
    -o output/my_data \
    --max-files 20 \
    --format alpaca \
    --split

# 5. 查看结果
ls output/my_data/
```

### 示例 2: 批量处理多个仓库

```bash
# 1. 创建仓库列表
cat > my_repos.txt << EOF
/Users/me/projects/repo1
/Users/me/projects/repo2
/Users/me/projects/repo3
EOF

# 2. 批量处理
python main.py batch-generate my_repos.txt \
    -o output/batch_data \
    --max-qa-per-repo 50 \
    --format alpaca \
    --split

# 3. 查看报告
cat output/batch_data/batch_report_*.md
```

### 示例 3: 自动发现 GitHub 仓库

```bash
# 1. 查看可用场景
python main.py auto-discover --list-scenarios

# 2. 搜索并生成数据
python main.py auto-discover \
    --scenario 金融科技 \
    --max-repos 5 \
    --auto-generate \
    --split

# 3. 查看结果
ls output/auto_discovered/
```

## 常用命令速查

| 功能 | 命令 |
|------|------|
| 分析仓库 | `python main.py analyze <repo_path>` |
| 生成问答对 | `python main.py generate-qa <repo_path> -o output` |
| 生成设计方案 | `python main.py generate-design <repo_path> "需求描述"` |
| 完整流程 | `python main.py full-pipeline <repo_path>` |
| 批量处理 | `python main.py batch-generate repos.txt` |
| 自动发现 | `python main.py auto-discover -s 场景 --auto-generate` |
| 查看帮助 | `python main.py --help` |

## 输出文件说明

```
output/
├── qa_dataset_train.alpaca    # 训练集（80%）
├── qa_dataset_valid.alpaca    # 验证集（10%）
├── qa_dataset_test.alpaca     # 测试集（10%）
├── README.md                   # 数据集说明卡
└── design_docs/               # 设计文档（如有）
```

## 下一步

- [批量处理指南](../user-guide/batch-processing.md) - 多仓库处理
- [微调指南](../user-guide/finetuning-guide.md) - 使用数据微调模型

