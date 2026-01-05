# 模型微调指南

本文档介绍如何使用生成的训练数据微调 Qwen 系列模型。

## 概述

支持两种微调方式：
1. **DashScope 在线微调**（推荐）- 无需 GPU，按使用付费
2. **本地 LoRA 微调** - 需要 GPU，完全控制

## DashScope 在线微调（推荐）

### 前置准备

#### 1. 获取 API Key

访问 [DashScope 控制台](https://dashscope.console.aliyun.com/) 获取 API Key。

#### 2. 设置环境变量

```bash
export DASHSCOPE_API_KEY='your-api-key-here'
```

或添加到 `.env` 文件：

```bash
echo "DASHSCOPE_API_KEY=your-api-key-here" >> .env
```

#### 3. 安装依赖

```bash
pip install dashscope pyyaml
```

### 方式一：自动化流程（推荐）

```bash
python scripts/finetuning/quickstart_finetune.py
```

脚本会自动完成：
- ✅ 检查依赖和 API Key
- ✅ 查找最新的训练数据
- ✅ 智能合并 QA 和 Design 数据
- ✅ 转换为 DashScope 格式
- ✅ 验证数据质量
- ✅ 创建微调配置
- ✅ 启动微调任务
- ✅ 监控训练进度

### 方式二：手动步骤

#### 步骤 1：合并数据（可选）

如果同时有 QA 和 Design 数据，建议先合并：

```bash
python scripts/data_processing/merge_qa_design.py \
    --qa-base output/complete_training/merged_qa_dataset_20260105 \
    --design-base output/complete_training/merged_design_dataset_20260105 \
    --output-base output/merged/merged_all_20260105 \
    --all-splits
```

#### 步骤 2：转换数据格式

```bash
# 转换训练集
python scripts/data_processing/convert_to_dashscope.py \
    output/complete_training/merged_qa_dataset_*_train.alpaca \
    -o output/dashscope/train.jsonl

# 转换验证集
python scripts/data_processing/convert_to_dashscope.py \
    output/complete_training/merged_qa_dataset_*_valid.alpaca \
    -o output/dashscope/valid.jsonl
```

#### 步骤 3：验证数据

```bash
python scripts/data_processing/validate_dashscope_data.py output/dashscope/train.jsonl
```

#### 步骤 4：开始微调

```bash
python scripts/finetuning/dashscope_finetune.py scripts/finetuning/finetune_config.yaml
```

#### 步骤 5：监控进度

```bash
python scripts/finetuning/monitor_finetune.py <job_id>
```

#### 步骤 6：评估模型

```bash
python scripts/evaluation/evaluate_finetuned_model.py \
    --model ft-qwen-turbo-xxxx \
    --test-file output/dashscope/test.jsonl
```

### 微调参数建议

| 数据量 | Epochs | Batch Size | Learning Rate | 预计时间 | 预计成本 |
|--------|--------|------------|---------------|----------|----------|
| < 500 条 | 5 | 8 | 2e-5 | 10-20分钟 | ~¥3-5 |
| 500-1500 条 | 3-4 | 16 | 2e-5 | 20-40分钟 | ~¥5-10 |
| 1500-3000 条 | 3 | 16 | 2e-5 | 40-60分钟 | ~¥10-15 |
| > 3000 条 | 2-3 | 16-32 | 1e-5 | 60-120分钟 | ~¥15-30 |

### 使用微调后的模型

```python
from dashscope import Generation
import os

os.environ['DASHSCOPE_API_KEY'] = 'your-api-key'

response = Generation.call(
    model='ft-qwen-turbo-xxxx-yyyy-zzzz',  # 你的模型 ID
    prompt='解释这段代码的功能：\ndef fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)',
    max_tokens=500
)

print(response.output.text)
```

## 本地 LoRA 微调（需要 GPU）

### 环境要求

- NVIDIA GPU（推荐 16GB+ 显存）
- CUDA 11.8+
- PyTorch 2.0+

### 安装依赖

```bash
pip install torch transformers peft datasets accelerate
```

### 快速验证

```bash
python main.py validate output/datasets/qa_dataset.jsonl --epochs 1 --samples 100
```

### 完整微调流程

```python
from src.finetuning import FineTuner

trainer = FineTuner()
result = trainer.train(
    train_data="output/datasets/qa_dataset_train.jsonl",
    valid_data="output/datasets/qa_dataset_valid.jsonl",
    output_dir="output/models",
    num_epochs=3,
    batch_size=4,
    learning_rate=2e-5,
    lora_r=16,
    lora_alpha=32
)
```

## 数据格式要求

### DashScope 格式

```json
{"messages": [{"role": "user", "content": "问题"}, {"role": "assistant", "content": "回答"}]}
```

### Alpaca 格式（本地微调）

```json
{"instruction": "问题", "input": "上下文", "output": "回答"}
```

## 常见问题

### Q: DashScope 微调失败怎么办？

**A:**
1. 检查 API Key 是否有效
2. 验证数据格式：`python scripts/data_processing/validate_dashscope_data.py data.jsonl`
3. 检查数据量是否满足最小要求（通常 > 100 条）

### Q: 如何选择微调的模型？

**A:**
- `qwen-turbo` - 最快速度，最低成本，适合测试
- `qwen-plus` - 平衡性能和成本
- `qwen-max` - 最强效果，成本最高

### Q: 微调后效果不好怎么办？

**A:**
1. 增加数据量（建议 500+ 条）
2. 提高数据质量（检查数据验证报告）
3. 调整超参数（尝试更多 epochs 或更低 learning rate）
4. 合并 QA 和 Design 数据提高泛化性

### Q: 本地微调显存不足？

**A:**
1. 减小 batch_size
2. 使用梯度累积
3. 使用更小的模型
4. 启用 8-bit 或 4-bit 量化

## 相关文档

- [数据格式说明](data-formats.md) - 各种数据格式详解
- [批量处理指南](batch-processing.md) - 生成更多训练数据
- [API 参考 - DashScope](../api-reference/dashscope-api.md) - DashScope API 详解

