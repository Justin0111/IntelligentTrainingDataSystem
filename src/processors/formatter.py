"""
数据格式化器模块
将训练数据格式化为各种输出格式
"""

import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from dataclasses import asdict
from datetime import datetime

from ..config import get_config, ProcessorConfig
from ..generators.qa_generator import QAPair
from ..generators.design_generator import DesignProposal
from ..utils.helpers import save_json, save_jsonl

logger = logging.getLogger(__name__)


class DataFormatter:
    """
    数据格式化器
    
    支持多种输出格式：JSONL, JSON, CSV, Alpaca, ShareGPT 等
    """
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """
        初始化格式化器
        
        Args:
            config: 处理器配置
        """
        self.config = config or get_config().processor
    
    def format_qa_pairs(
        self,
        qa_pairs: List[QAPair],
        format_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        格式化问答对数据
        
        Args:
            qa_pairs: 问答对列表
            format_type: 输出格式类型
            
        Returns:
            格式化后的数据列表
        """
        format_type = format_type or self.config.output_format
        
        formatters = {
            "jsonl": self._format_qa_jsonl,
            "json": self._format_qa_json,
            "alpaca": self._format_qa_alpaca,
            "sharegpt": self._format_qa_sharegpt,
            "openai": self._format_qa_openai,
        }
        
        formatter = formatters.get(format_type, self._format_qa_jsonl)
        return [formatter(qa) for qa in qa_pairs]
    
    def format_design_proposals(
        self,
        designs: List[DesignProposal],
        format_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        格式化设计方案数据
        
        Args:
            designs: 设计方案列表
            format_type: 输出格式类型
            
        Returns:
            格式化后的数据列表
        """
        format_type = format_type or self.config.output_format
        
        formatters = {
            "jsonl": self._format_design_jsonl,
            "json": self._format_design_json,
            "alpaca": self._format_design_alpaca,
            "sharegpt": self._format_design_sharegpt,
        }
        
        formatter = formatters.get(format_type, self._format_design_jsonl)
        return [formatter(design) for design in designs]
    
    # QA 格式化方法
    def _format_qa_jsonl(self, qa: QAPair) -> Dict[str, Any]:
        """JSONL 格式（完整数据）"""
        return qa.to_dict()
    
    def _format_qa_json(self, qa: QAPair) -> Dict[str, Any]:
        """JSON 格式（完整数据）"""
        return qa.to_dict()
    
    def _format_qa_alpaca(self, qa: QAPair) -> Dict[str, Any]:
        """
        Alpaca 格式
        适用于 Stanford Alpaca 风格的微调
        """
        # 构建输入上下文
        input_context = ""
        if qa.code_context.get("code_snippet"):
            input_context = f"代码上下文：\n```\n{qa.code_context['code_snippet']}\n```"
        
        # 构建包含推理过程的输出
        reasoning_text = ""
        if qa.reasoning_trace:
            steps = [f"步骤{r.step}: {r.thought}" for r in qa.reasoning_trace]
            reasoning_text = "推理过程：\n" + "\n".join(steps) + "\n\n"
        
        return {
            "instruction": qa.question,
            "input": input_context,
            "output": reasoning_text + qa.answer
        }
    
    def _format_qa_sharegpt(self, qa: QAPair) -> Dict[str, Any]:
        """
        ShareGPT 格式
        多轮对话格式
        """
        conversations = []
        
        # 用户问题
        user_content = qa.question
        if qa.code_context.get("code_snippet"):
            user_content += f"\n\n代码上下文：\n```\n{qa.code_context['code_snippet']}\n```"
        
        conversations.append({
            "from": "human",
            "value": user_content
        })
        
        # 助手回答（包含推理过程）
        assistant_content = ""
        if qa.reasoning_trace:
            assistant_content = "让我来分析这个问题：\n\n"
            for r in qa.reasoning_trace:
                assistant_content += f"**步骤 {r.step}**: {r.thought}\n"
            assistant_content += f"\n**结论**：{qa.answer}"
        else:
            assistant_content = qa.answer
        
        conversations.append({
            "from": "gpt",
            "value": assistant_content
        })
        
        return {
            "id": qa.id,
            "conversations": conversations
        }
    
    def _format_qa_openai(self, qa: QAPair) -> Dict[str, Any]:
        """
        OpenAI 微调格式
        适用于 OpenAI 的微调 API
        """
        messages = []
        
        # 系统消息
        messages.append({
            "role": "system",
            "content": "你是一个专业的代码分析助手，能够准确理解代码并提供详细的解释。"
        })
        
        # 用户消息
        user_content = qa.question
        if qa.code_context.get("code_snippet"):
            user_content += f"\n\n```\n{qa.code_context['code_snippet']}\n```"
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        # 助手消息
        assistant_content = qa.answer
        if qa.reasoning_trace:
            reasoning = "\n".join([f"{r.step}. {r.thought}" for r in qa.reasoning_trace])
            assistant_content = f"分析过程：\n{reasoning}\n\n结论：{qa.answer}"
        
        messages.append({
            "role": "assistant",
            "content": assistant_content
        })
        
        return {"messages": messages}
    
    # Design 格式化方法
    def _format_design_jsonl(self, design: DesignProposal) -> Dict[str, Any]:
        """JSONL 格式（完整数据）"""
        return design.to_dict()
    
    def _format_design_json(self, design: DesignProposal) -> Dict[str, Any]:
        """JSON 格式（完整数据）"""
        return design.to_dict()
    
    def _format_design_alpaca(self, design: DesignProposal) -> Dict[str, Any]:
        """Alpaca 格式"""
        # 构建输入（架构上下文）
        input_context = ""
        if design.architecture_context:
            input_context = f"现有架构信息：\n{json.dumps(design.architecture_context, ensure_ascii=False, indent=2)}"
        
        # 构建输出（包含推理和设计）
        output_parts = []
        
        # 推理过程
        if design.reasoning_trace:
            output_parts.append("## 分析过程")
            for r in design.reasoning_trace:
                output_parts.append(f"{r.step}. {r.thought}")
        
        # 方案概述
        output_parts.append(f"\n## 方案概述\n{design.overview}")
        
        # 组件设计
        if design.components:
            output_parts.append("\n## 组件设计")
            for comp in design.components:
                output_parts.append(f"- **{comp.name}** ({comp.component_type}): {comp.responsibility}")
        
        return {
            "instruction": f"请为以下需求设计一个解决方案：{design.requirement}",
            "input": input_context,
            "output": "\n".join(output_parts)
        }
    
    def _format_design_sharegpt(self, design: DesignProposal) -> Dict[str, Any]:
        """ShareGPT 格式"""
        conversations = []
        
        # 用户需求
        user_content = f"我需要在现有项目中实现这个功能：{design.requirement}"
        if design.architecture_context:
            user_content += f"\n\n项目架构：\n```json\n{json.dumps(design.architecture_context, ensure_ascii=False, indent=2)}\n```"
        
        conversations.append({
            "from": "human",
            "value": user_content
        })
        
        # 助手设计方案
        assistant_parts = ["我来为你设计一个解决方案：\n"]
        
        # 推理过程
        if design.reasoning_trace:
            assistant_parts.append("**设计分析**：")
            for r in design.reasoning_trace:
                assistant_parts.append(f"  {r.step}. {r.thought}")
        
        assistant_parts.append(f"\n**方案概述**：\n{design.overview}")
        
        if design.components:
            assistant_parts.append("\n**核心组件**：")
            for comp in design.components:
                assistant_parts.append(f"- `{comp.name}`: {comp.responsibility}")
        
        conversations.append({
            "from": "gpt",
            "value": "\n".join(assistant_parts)
        })
        
        return {
            "id": design.id,
            "conversations": conversations
        }
    
    # 输出方法
    def save_qa_dataset(
        self,
        qa_pairs: List[QAPair],
        output_path: Path,
        format_type: Optional[str] = None,
        split_ratio: Optional[Dict[str, float]] = None
    ) -> Dict[str, Path]:
        """
        保存问答对数据集
        
        Args:
            qa_pairs: 问答对列表
            output_path: 输出路径
            format_type: 输出格式
            split_ratio: 数据集划分比例 {"train": 0.8, "valid": 0.1, "test": 0.1}
            
        Returns:
            输出文件路径字典
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        format_type = format_type or self.config.output_format
        
        # 格式化数据
        formatted_data = self.format_qa_pairs(qa_pairs, format_type)
        
        output_files = {}
        
        if split_ratio:
            # 划分数据集
            splits = self._split_dataset(formatted_data, split_ratio)
            
            for split_name, split_data in splits.items():
                split_path = output_path.parent / f"{output_path.stem}_{split_name}{output_path.suffix}"
                self._save_data(split_data, split_path, format_type)
                output_files[split_name] = split_path
                logger.info(f"保存 {split_name} 数据集: {len(split_data)} 条 -> {split_path}")
        else:
            # 保存完整数据集
            self._save_data(formatted_data, output_path, format_type)
            output_files["full"] = output_path
            logger.info(f"保存数据集: {len(formatted_data)} 条 -> {output_path}")
        
        return output_files
    
    def save_design_dataset(
        self,
        designs: List[DesignProposal],
        output_path: Path,
        format_type: Optional[str] = None,
        split_ratio: Optional[Dict[str, float]] = None
    ) -> Dict[str, Path]:
        """
        保存设计方案数据集
        
        Args:
            designs: 设计方案列表
            output_path: 输出路径
            format_type: 输出格式
            split_ratio: 数据集划分比例 {"train": 0.8, "valid": 0.1, "test": 0.1}
            
        Returns:
            输出文件路径字典
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        format_type = format_type or self.config.output_format
        
        # 格式化数据
        formatted_data = self.format_design_proposals(designs, format_type)
        
        output_files = {}
        
        if split_ratio:
            # 划分数据集
            splits = self._split_dataset(formatted_data, split_ratio)
            
            for split_name, split_data in splits.items():
                split_path = output_path.parent / f"{output_path.stem}_{split_name}{output_path.suffix}"
                self._save_data(split_data, split_path, format_type)
                output_files[split_name] = split_path
                logger.info(f"保存 {split_name} 设计方案数据集: {len(split_data)} 条 -> {split_path}")
        else:
            # 保存完整数据集
            self._save_data(formatted_data, output_path, format_type)
            output_files["full"] = output_path
            logger.info(f"保存设计方案数据集: {len(formatted_data)} 条 -> {output_path}")
        
        return output_files
    
    def _save_data(
        self,
        data: List[Dict],
        output_path: Path,
        format_type: str
    ):
        """保存数据到文件"""
        if format_type in ["jsonl", "alpaca", "sharegpt", "openai"]:
            save_jsonl(data, output_path)
        elif format_type == "json":
            save_json(data, output_path)
        elif format_type == "csv":
            self._save_csv(data, output_path)
        else:
            # 默认使用 JSONL
            save_jsonl(data, output_path)
    
    def _save_csv(self, data: List[Dict], output_path: Path):
        """保存为 CSV 格式"""
        if not data:
            return
        
        # 展平嵌套字典
        flattened = []
        for item in data:
            flat = self._flatten_dict(item)
            flattened.append(flat)
        
        # 获取所有列名
        columns = set()
        for item in flattened:
            columns.update(item.keys())
        columns = sorted(columns)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(flattened)
    
    def _flatten_dict(
        self,
        d: Dict,
        parent_key: str = '',
        sep: str = '.'
    ) -> Dict:
        """展平嵌套字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                items.append((new_key, json.dumps(v, ensure_ascii=False)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _split_dataset(
        self,
        data: List[Dict],
        ratio: Dict[str, float]
    ) -> Dict[str, List[Dict]]:
        """划分数据集"""
        import random
        
        # 打乱数据
        shuffled = data.copy()
        random.shuffle(shuffled)
        
        total = len(shuffled)
        splits = {}
        start = 0
        
        for split_name, split_ratio in ratio.items():
            count = int(total * split_ratio)
            if split_name == list(ratio.keys())[-1]:
                # 最后一个划分获取剩余所有数据
                splits[split_name] = shuffled[start:]
            else:
                splits[split_name] = shuffled[start:start + count]
                start += count
        
        return splits
    
    def create_dataset_card(
        self,
        qa_pairs: List[QAPair],
        designs: List[DesignProposal],
        output_path: Path
    ) -> Path:
        """
        创建数据集说明卡片
        
        Args:
            qa_pairs: 问答对列表
            designs: 设计方案列表
            output_path: 输出目录
            
        Returns:
            说明文件路径
        """
        output_path = Path(output_path)
        card_path = output_path / "README.md"
        
        # 统计信息
        qa_types = {}
        for qa in qa_pairs:
            t = qa.question_type
            qa_types[t] = qa_types.get(t, 0) + 1
        
        languages = {}
        for qa in qa_pairs:
            lang = qa.metadata.get("language", "unknown")
            languages[lang] = languages.get(lang, 0) + 1
        
        # 生成说明
        content = f"""# 代码训练数据集

## 概述

本数据集用于训练代码理解和设计方案生成模型。

- 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 问答对数量: {len(qa_pairs)}
- 设计方案数量: {len(designs)}

## 数据格式

### 问答对 (QA Pairs)

每个问答对包含：
- `id`: 唯一标识符
- `question`: 问题文本
- `answer`: 答案文本
- `question_type`: 问题类型
- `code_context`: 代码上下文
- `reasoning_trace`: 推理步骤
- `metadata`: 元数据

问题类型分布：
{self._format_stats(qa_types)}

编程语言分布：
{self._format_stats(languages)}

### 设计方案 (Design Proposals)

每个设计方案包含：
- `id`: 唯一标识符
- `requirement`: 需求描述
- `overview`: 方案概述
- `components`: 组件设计
- `reasoning_trace`: 推理步骤
- `integration_points`: 集成点

## 使用说明

### 加载数据

```python
import json

# 加载 JSONL 格式
with open('qa_dataset.jsonl', 'r') as f:
    qa_data = [json.loads(line) for line in f]

# 加载 JSON 格式
with open('design_dataset.json', 'r') as f:
    design_data = json.load(f)
```

### 转换为 HuggingFace Dataset

```python
from datasets import Dataset

dataset = Dataset.from_list(qa_data)
```

## 许可证

本数据集仅供学习和研究使用。
"""
        
        card_path.write_text(content, encoding='utf-8')
        logger.info(f"创建数据集说明: {card_path}")
        
        return card_path
    
    def _format_stats(self, stats: Dict[str, int]) -> str:
        """格式化统计信息"""
        lines = []
        for k, v in sorted(stats.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {k}: {v}")
        return '\n'.join(lines)

