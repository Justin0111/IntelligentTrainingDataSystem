# 批量处理指南

本文档详细介绍如何使用批量处理功能从多个代码仓库生成训练数据。

## 功能概述

批量处理允许您一次性从多个代码仓库生成训练数据，并自动进行数据平衡、合并和去重，最终生成统一的训练数据集。

**核心优势：**
- ✅ 提高模型泛化能力（避免过拟合到单一项目）
- ✅ 增加数据多样性（覆盖不同架构和领域）
- ✅ 自动数据平衡（防止某个项目主导数据集）
- ✅ 一键生成完整数据集（节省时间）

## 快速开始

### 步骤 1: 准备仓库列表

**JSON 格式 (`my_repos.json`)：**

```json
{
  "repositories": [
    {"path": "/Users/me/projects/repo1", "name": "项目1"},
    {"path": "/Users/me/projects/repo2", "name": "项目2"},
    {"path": "/Users/me/projects/repo3", "name": "项目3"}
  ]
}
```

**文本格式 (`my_repos.txt`)：**

```text
/Users/me/projects/repo1
/Users/me/projects/repo2
/Users/me/projects/repo3
```

### 步骤 2: 执行批量处理

```bash
python main.py batch-generate my_repos.json \
    --output output/my_training_data \
    --max-qa-per-repo 100 \
    --format alpaca \
    --split
```

### 步骤 3: 查看结果

```bash
# 查看报告
cat output/my_training_data/batch_report_*.md

# 检查数据
head output/my_training_data/merged_qa_dataset_*_train.jsonl
```

## 命令参数详解

### 基本参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--output` | `-o` | 输出目录 | `output/batch` |
| `--max-files` | `-m` | 每个仓库最大处理文件数 | 30 |
| `--format` | `-f` | 输出格式 | `jsonl` |
| `--split` | - | 划分训练/验证/测试集 | False |

### 数据平衡参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--max-qa-per-repo` | 每个仓库最大 QA 数量 | 无限制 |
| `--max-design-per-repo` | 每个仓库最大设计方案数量 | 无限制 |
| `--balance-strategy` | 平衡策略 | `proportional` |

### 设计方案参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--requirements-file` | `-r` | 设计需求列表文件 |
| `--design-only` | - | 只生成设计方案，跳过 QA |

## 数据平衡策略

### proportional（比例平衡）⭐ 推荐

```bash
--balance-strategy proportional --max-qa-per-repo 80
```

**特点：**
- 限制每个仓库的最大数据量
- 保持各仓库的相对比例
- 防止单个仓库主导数据集

**适用场景：** 大多数情况

### uniform（均匀平衡）

```bash
--balance-strategy uniform
```

**特点：**
- 每个仓库贡献相同数量的数据
- 完全公平分配

**适用场景：** 所有仓库质量相当时

### weighted（加权平衡）

```bash
--balance-strategy weighted
```

**特点：**
- 根据仓库质量评分分配数据量
- 高质量仓库贡献更多

**适用场景：** 有明确的仓库质量评分时

## 输出文件说明

```
output/batch/
├── merged_qa_dataset_*.jsonl          # 完整 QA 数据集
├── merged_qa_dataset_*_train.jsonl    # 训练集 (使用 --split 时)
├── merged_qa_dataset_*_valid.jsonl    # 验证集
├── merged_qa_dataset_*_test.jsonl     # 测试集
├── merged_design_dataset_*.jsonl      # 设计方案数据集
├── batch_report_*.json                # JSON 格式统计报告
├── batch_report_*.md                  # Markdown 格式报告
├── README.md                          # 数据集说明卡
└── design_docs/                       # 设计文档示例
```

## 命令示例

### 基础批量处理

```bash
python main.py batch-generate repos.json -o output/batch
```

### 推荐配置（适合大多数场景）

```bash
python main.py batch-generate repos.json \
    --output output/finetune_data \
    --max-qa-per-repo 80 \
    --max-design-per-repo 15 \
    --balance-strategy proportional \
    --format alpaca \
    --split \
    --max-files 50
```

### 带设计需求生成

```bash
python main.py batch-generate repos.json \
    --output output/with_design \
    --requirements-file requirements.txt \
    --max-qa-per-repo 100 \
    --max-design-per-repo 20
```

### 只生成设计方案

```bash
python main.py batch-generate repos.json \
    --output output/design_only \
    --design-only \
    --requirements-file requirements.txt
```

### 小规模测试

```bash
python main.py batch-generate repos.txt \
    --output output/test \
    --max-files 10 \
    --max-qa-per-repo 20
```

## 数据收集建议

### 推荐配置

```
总数据量建议：
  - QA 数据：500-2000 条
  - Design 数据：100-500 条
  - 总数据：600-2500 条

仓库选择：
  - 数量：5-10 个不同项目
  - 类型：不同业务领域（金融、电商、工具等）
  - 质量：代码结构清晰、有一定复杂度
  - 规模：大中小项目混合
  
数据比例：
  - QA：Design = 70:30 或 60:40
  - 单个仓库占比 < 30%
```

### max-qa-per-repo 设置建议

| 项目规模 | 文件数 | 推荐值 |
|----------|--------|--------|
| 小型项目 | < 50 | 30-50 |
| 中型项目 | 50-200 | 50-100 |
| 大型项目 | > 200 | 80-150 |

## 实用技巧

### 检查数据平衡度

```bash
# 查看平衡指标
cat output/batch/batch_report_*.json | jq '.balance_metrics'

# 查看各仓库贡献
cat output/batch/batch_report_*.json | jq '.by_repo'
```

### 查看数据样本

```python
import json

with open('output/batch/merged_qa_dataset_*_train.jsonl', 'r') as f:
    samples = [json.loads(line) for line in f][:3]

for i, s in enumerate(samples):
    print(f"\n样本 {i+1}:")
    print(f"问题: {s['question']}")
    print(f"来源: {s['metadata']['source_repo']}")
```

### 合并多个批次

```bash
python scripts/data_processing/merge_datasets.py \
    output/batch1/qa_dataset.jsonl \
    output/batch2/qa_dataset.jsonl \
    -o final_dataset.jsonl
```

## 常见问题

### Q: 需要多少个仓库？

**A:** 推荐 5-10 个不同领域的项目。太少会导致数据多样性不足，太多会增加处理时间。

### Q: 某个仓库处理失败怎么办？

**A:**
1. 检查 `batch_report_*.json` 中的 `processing_errors`
2. 单独处理该仓库：`python main.py generate-qa /path/to/repo`
3. 如果仍然失败，从列表中移除该仓库

### Q: 数据量太少怎么办？

**A:**
- 增加 `--max-files` 参数
- 增加仓库数量
- 移除或增大 `--max-qa-per-repo` 限制

### Q: 如何验证数据集质量？

**A:**
```bash
python main.py validate output/batch/merged_qa_dataset_*_train.jsonl \
    --epochs 1 --samples 100
```

## 相关文档

- [自动发现功能](auto-discovery.md) - 自动搜索 GitHub 仓库
- [数据格式说明](data-formats.md) - 输出格式详解
- [微调指南](finetuning-guide.md) - 使用数据微调模型

