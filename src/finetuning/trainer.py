"""
微调训练器模块
使用 LoRA 进行模型微调，验证数据集效果
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from ..config import get_config, FineTuningConfig
from ..utils.helpers import load_jsonl, save_json

logger = logging.getLogger(__name__)


@dataclass
class TrainingMetrics:
    """训练指标"""
    epoch: int
    train_loss: float
    eval_loss: Optional[float] = None
    learning_rate: float = 0.0
    step: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "epoch": self.epoch,
            "train_loss": self.train_loss,
            "eval_loss": self.eval_loss,
            "learning_rate": self.learning_rate,
            "step": self.step
        }


@dataclass
class EvaluationResult:
    """评估结果"""
    accuracy: float
    perplexity: float
    sample_outputs: List[Dict[str, str]] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "accuracy": self.accuracy,
            "perplexity": self.perplexity,
            "sample_outputs": self.sample_outputs,
            "metrics": self.metrics
        }


class FineTuner:
    """
    微调训练器
    
    使用 LoRA 技术对小型模型进行高效微调
    """
    
    def __init__(self, config: Optional[FineTuningConfig] = None):
        """
        初始化微调训练器
        
        Args:
            config: 微调配置
        """
        self.config = config or get_config().finetuning
        self._model = None
        self._tokenizer = None
        self._trainer = None
        self._is_initialized = False
    
    def _check_dependencies(self) -> bool:
        """检查必要的依赖是否已安装"""
        try:
            import torch
            import transformers
            import peft
            import datasets
            return True
        except ImportError as e:
            logger.error(f"缺少必要的依赖: {e}")
            logger.info("请运行: pip install torch transformers peft datasets accelerate")
            return False
    
    def initialize(self, model_name: Optional[str] = None):
        """
        初始化模型和分词器
        
        Args:
            model_name: 模型名称，如果为None则使用配置中的模型
        """
        if not self._check_dependencies():
            raise RuntimeError("缺少必要的依赖，请安装 torch, transformers, peft, datasets")
        
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        
        model_name = model_name or self.config.base_model
        logger.info(f"加载模型: {model_name}")
        
        # 加载分词器
        self._tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="right"
        )
        
        # 确保有 pad token
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        
        # 检查是否有 GPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"使用设备: {device}")
        
        # 加载模型
        if device == "cuda":
            # 使用量化加载以节省显存
            try:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    quantization_config=quantization_config,
                    device_map="auto",
                    trust_remote_code=True
                )
                self._model = prepare_model_for_kbit_training(self._model)
            except Exception as e:
                logger.warning(f"量化加载失败: {e}，尝试正常加载")
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True
                )
        else:
            self._model = AutoModelForCausalLM.from_pretrained(
                model_name,
                trust_remote_code=True
            )
        
        # 配置 LoRA
        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        )
        
        self._model = get_peft_model(self._model, lora_config)
        self._model.print_trainable_parameters()
        
        self._is_initialized = True
        logger.info("模型初始化完成")
    
    def prepare_dataset(
        self,
        data_path: Union[str, Path],
        format_type: str = "alpaca"
    ):
        """
        准备训练数据集
        
        Args:
            data_path: 数据文件路径
            format_type: 数据格式类型
            
        Returns:
            处理后的数据集
        """
        from datasets import Dataset
        
        data_path = Path(data_path)
        logger.info(f"加载数据集: {data_path}")
        
        # 加载数据
        if data_path.suffix == ".jsonl":
            data = load_jsonl(data_path)
        else:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        # 转换为训练格式
        formatted_data = []
        for item in data:
            text = self._format_training_example(item, format_type)
            if text:
                formatted_data.append({"text": text})
        
        dataset = Dataset.from_list(formatted_data)
        logger.info(f"数据集大小: {len(dataset)}")
        
        return dataset
    
    def _format_training_example(
        self,
        item: Dict,
        format_type: str
    ) -> Optional[str]:
        """格式化单个训练样本"""
        if format_type == "alpaca":
            instruction = item.get("instruction", "")
            input_text = item.get("input", "")
            output = item.get("output", "")
            
            if input_text:
                text = f"### 指令:\n{instruction}\n\n### 输入:\n{input_text}\n\n### 回答:\n{output}"
            else:
                text = f"### 指令:\n{instruction}\n\n### 回答:\n{output}"
            
            return text
        
        elif format_type == "sharegpt":
            conversations = item.get("conversations", [])
            text_parts = []
            
            for conv in conversations:
                role = conv.get("from", "")
                value = conv.get("value", "")
                
                if role == "human":
                    text_parts.append(f"### 用户:\n{value}")
                elif role == "gpt":
                    text_parts.append(f"### 助手:\n{value}")
            
            return "\n\n".join(text_parts)
        
        elif format_type == "qa":
            question = item.get("question", "")
            answer = item.get("answer", "")
            
            return f"### 问题:\n{question}\n\n### 回答:\n{answer}"
        
        return None
    
    def tokenize_dataset(self, dataset, max_length: int = 512):
        """
        对数据集进行分词
        
        Args:
            dataset: 原始数据集
            max_length: 最大序列长度
            
        Returns:
            分词后的数据集
        """
        def tokenize_function(examples):
            return self._tokenizer(
                examples["text"],
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_tensors="pt"
            )
        
        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names
        )
        
        return tokenized_dataset
    
    def train(
        self,
        train_dataset,
        eval_dataset=None,
        output_dir: Optional[Path] = None,
        **kwargs
    ) -> List[TrainingMetrics]:
        """
        执行训练
        
        Args:
            train_dataset: 训练数据集
            eval_dataset: 验证数据集
            output_dir: 输出目录
            **kwargs: 额外的训练参数
            
        Returns:
            训练指标列表
        """
        if not self._is_initialized:
            raise RuntimeError("模型未初始化，请先调用 initialize()")
        
        from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling
        
        output_dir = output_dir or Path("output/models/finetuned")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 训练参数
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=kwargs.get("num_epochs", self.config.num_epochs),
            per_device_train_batch_size=kwargs.get("batch_size", self.config.batch_size),
            gradient_accumulation_steps=kwargs.get(
                "gradient_accumulation_steps", 
                self.config.gradient_accumulation_steps
            ),
            learning_rate=kwargs.get("learning_rate", self.config.learning_rate),
            warmup_ratio=0.1,
            logging_steps=10,
            save_steps=kwargs.get("save_steps", 100),
            eval_steps=kwargs.get("eval_steps", self.config.eval_steps),
            evaluation_strategy="steps" if eval_dataset else "no",
            save_total_limit=2,
            load_best_model_at_end=eval_dataset is not None,
            fp16=True,
            report_to="none",  # 禁用 wandb 等
        )
        
        # 数据整理器
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self._tokenizer,
            mlm=False
        )
        
        # 创建训练器
        self._trainer = Trainer(
            model=self._model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )
        
        logger.info("开始训练...")
        train_result = self._trainer.train()
        
        # 保存模型
        self._trainer.save_model()
        self._tokenizer.save_pretrained(output_dir)
        
        # 收集训练指标
        metrics = []
        if hasattr(train_result, "metrics"):
            metrics.append(TrainingMetrics(
                epoch=training_args.num_train_epochs,
                train_loss=train_result.metrics.get("train_loss", 0),
                step=train_result.global_step
            ))
        
        logger.info(f"训练完成，模型保存至: {output_dir}")
        return metrics
    
    def evaluate(
        self,
        eval_dataset,
        num_samples: int = 5
    ) -> EvaluationResult:
        """
        评估模型
        
        Args:
            eval_dataset: 评估数据集
            num_samples: 生成样本数量
            
        Returns:
            EvaluationResult 评估结果
        """
        if not self._is_initialized:
            raise RuntimeError("模型未初始化")
        
        import torch
        
        logger.info("开始评估...")
        
        # 计算困惑度
        self._model.eval()
        total_loss = 0
        total_tokens = 0
        
        with torch.no_grad():
            for i, example in enumerate(eval_dataset):
                if i >= 100:  # 限制评估样本数
                    break
                
                input_ids = torch.tensor([example["input_ids"]])
                if torch.cuda.is_available():
                    input_ids = input_ids.cuda()
                
                outputs = self._model(input_ids, labels=input_ids)
                total_loss += outputs.loss.item() * input_ids.size(1)
                total_tokens += input_ids.size(1)
        
        avg_loss = total_loss / total_tokens if total_tokens > 0 else 0
        perplexity = torch.exp(torch.tensor(avg_loss)).item()
        
        # 生成样本输出
        sample_outputs = self._generate_samples(eval_dataset, num_samples)
        
        result = EvaluationResult(
            accuracy=0.0,  # 需要根据具体任务计算
            perplexity=perplexity,
            sample_outputs=sample_outputs,
            metrics={"avg_loss": avg_loss}
        )
        
        logger.info(f"评估完成: Perplexity = {perplexity:.4f}")
        return result
    
    def _generate_samples(
        self,
        dataset,
        num_samples: int
    ) -> List[Dict[str, str]]:
        """生成样本输出"""
        import torch
        
        samples = []
        self._model.eval()
        
        for i, example in enumerate(dataset):
            if i >= num_samples:
                break
            
            # 获取原始文本
            original_text = self._tokenizer.decode(
                example["input_ids"],
                skip_special_tokens=True
            )
            
            # 截取问题部分作为输入
            if "### 回答:" in original_text:
                prompt = original_text.split("### 回答:")[0] + "### 回答:\n"
            else:
                prompt = original_text[:len(original_text)//2]
            
            # 生成
            input_ids = self._tokenizer.encode(prompt, return_tensors="pt")
            if torch.cuda.is_available():
                input_ids = input_ids.cuda()
            
            with torch.no_grad():
                outputs = self._model.generate(
                    input_ids,
                    max_new_tokens=200,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self._tokenizer.pad_token_id
                )
            
            generated_text = self._tokenizer.decode(
                outputs[0],
                skip_special_tokens=True
            )
            
            samples.append({
                "prompt": prompt[:500],
                "generated": generated_text[len(prompt):],
                "reference": original_text.split("### 回答:")[-1] if "### 回答:" in original_text else ""
            })
        
        return samples
    
    def quick_validate(
        self,
        data_path: Union[str, Path],
        output_dir: Optional[Path] = None,
        num_epochs: int = 1,
        max_samples: int = 100
    ) -> Dict[str, Any]:
        """
        快速验证数据集效果
        
        Args:
            data_path: 数据文件路径
            output_dir: 输出目录
            num_epochs: 训练轮数
            max_samples: 最大样本数
            
        Returns:
            验证结果
        """
        logger.info("开始快速验证...")
        
        # 初始化模型
        if not self._is_initialized:
            self.initialize()
        
        # 准备数据
        dataset = self.prepare_dataset(data_path)
        
        # 限制样本数量
        if len(dataset) > max_samples:
            dataset = dataset.select(range(max_samples))
        
        # 划分训练集和验证集
        train_size = int(len(dataset) * 0.9)
        train_dataset = dataset.select(range(train_size))
        eval_dataset = dataset.select(range(train_size, len(dataset)))
        
        # 分词
        train_dataset = self.tokenize_dataset(train_dataset)
        eval_dataset = self.tokenize_dataset(eval_dataset)
        
        # 训练
        output_dir = output_dir or Path("output/models/quick_validate")
        metrics = self.train(
            train_dataset,
            eval_dataset,
            output_dir,
            num_epochs=num_epochs
        )
        
        # 评估
        eval_result = self.evaluate(eval_dataset)
        
        # 保存结果
        result = {
            "training_metrics": [m.to_dict() for m in metrics],
            "evaluation": eval_result.to_dict(),
            "config": {
                "model": self.config.base_model,
                "num_epochs": num_epochs,
                "max_samples": max_samples
            },
            "timestamp": datetime.now().isoformat()
        }
        
        result_path = output_dir / "validation_result.json"
        save_json(result, result_path)
        
        logger.info(f"快速验证完成，结果保存至: {result_path}")
        return result
    
    def export_model(
        self,
        output_dir: Path,
        merge_adapter: bool = True
    ) -> Path:
        """
        导出微调后的模型
        
        Args:
            output_dir: 输出目录
            merge_adapter: 是否合并 adapter 权重
            
        Returns:
            导出路径
        """
        if not self._is_initialized:
            raise RuntimeError("模型未初始化")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if merge_adapter:
            # 合并 LoRA 权重到基础模型
            logger.info("合并 adapter 权重...")
            merged_model = self._model.merge_and_unload()
            merged_model.save_pretrained(output_dir)
        else:
            # 只保存 adapter
            self._model.save_pretrained(output_dir)
        
        self._tokenizer.save_pretrained(output_dir)
        
        logger.info(f"模型导出至: {output_dir}")
        return output_dir

