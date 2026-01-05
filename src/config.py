"""
配置管理模块
使用 pydantic-settings 进行配置管理，支持环境变量和 .env 文件
"""

from pathlib import Path
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# 确保加载 .env 文件
load_dotenv()


class LLMConfig(BaseSettings):
    """LLM API 配置"""
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    provider: str = Field(default="qwen", description="LLM 提供商: qwen, openai, ollama")
    api_key: Optional[str] = Field(default=None, description="API 密钥")
    base_url: Optional[str] = Field(default=None, description="API 基础URL (用于自定义端点)")
    model_name: str = Field(default="qwen-turbo", description="模型名称")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")
    max_tokens: int = Field(default=4096, description="最大生成token数")
    timeout: int = Field(default=120, description="API 超时时间(秒)")
    max_retries: int = Field(default=3, description="最大重试次数")
    sanitize_code: bool = Field(default=True, description="是否清理代码中的敏感信息")


class ParserConfig(BaseSettings):
    """代码解析配置"""
    model_config = SettingsConfigDict(
        env_prefix="PARSER_",
        env_ignore_empty=True
    )
    
    # 支持的编程语言
    supported_languages: List[str] = Field(
        default_factory=lambda: ["python", "javascript", "typescript", "java"],
        description="支持解析的编程语言列表"
    )
    
    # 文件过滤
    ignore_patterns: List[str] = Field(
        default_factory=lambda: [
            "*.pyc", "__pycache__", ".git", ".svn", 
            "node_modules", "venv", ".venv", "env",
            "*.min.js", "*.min.css", "dist", "build",
            ".idea", ".vscode", "*.egg-info"
        ],
        description="忽略的文件/目录模式"
    )
    
    # 文件大小限制
    max_file_size: int = Field(default=1024 * 1024, description="最大文件大小(字节)")
    
    # 解析深度
    max_depth: int = Field(default=10, description="目录遍历最大深度")


class GeneratorConfig(BaseSettings):
    """数据生成配置"""
    model_config = SettingsConfigDict(
        env_prefix="GENERATOR_",
        env_ignore_empty=True,  # 忽略空的环境变量
        validate_default=True,
        use_enum_values=True
    )
    
    # 问答对生成配置
    qa_per_file: int = Field(default=3, description="每个文件生成的问答对数量")
    qa_types: Optional[List[str]] = Field(
        default=None,
        description="问答类型"
    )
    
    @field_validator('qa_types', mode='before')
    @classmethod
    def set_default_qa_types(cls, v):
        """设置默认的问答类型"""
        if v is None or v == '' or v == []:
            return ["function_explanation", "business_logic", "code_flow", "error_handling"]
        return v
    
    # 设计方案生成配置
    design_complexity_levels: List[str] = Field(
        default_factory=lambda: ["simple", "medium", "complex"],
        description="设计方案复杂度级别"
    )
    
    # 推理链配置
    min_reasoning_steps: int = Field(default=3, description="最小推理步骤数")
    max_reasoning_steps: int = Field(default=8, description="最大推理步骤数")
    
    # 批处理配置
    batch_size: int = Field(default=5, description="批处理大小")


class ProcessorConfig(BaseSettings):
    """数据处理配置"""
    model_config = SettingsConfigDict(
        env_prefix="PROCESSOR_",
        env_ignore_empty=True
    )
    
    # 数据验证
    min_question_length: int = Field(default=10, description="最小问题长度")
    min_answer_length: int = Field(default=50, description="最小答案长度")
    
    # 输出格式
    output_format: str = Field(default="jsonl", description="输出格式: jsonl, json, csv")
    
    # 数据清洗
    remove_duplicates: bool = Field(default=True, description="是否去重")
    normalize_whitespace: bool = Field(default=True, description="是否标准化空白字符")


class FineTuningConfig(BaseSettings):
    """微调配置"""
    model_config = SettingsConfigDict(
        env_prefix="FINETUNE_",
        env_ignore_empty=True
    )
    
    # 基础模型
    base_model: str = Field(default="Qwen/Qwen2.5-1.5B", description="基础模型")
    
    # LoRA 配置
    lora_r: int = Field(default=8, description="LoRA rank")
    lora_alpha: int = Field(default=16, description="LoRA alpha")
    lora_dropout: float = Field(default=0.05, description="LoRA dropout")
    
    # 训练参数
    learning_rate: float = Field(default=2e-4, description="学习率")
    num_epochs: int = Field(default=3, description="训练轮数")
    batch_size: int = Field(default=4, description="批次大小")
    gradient_accumulation_steps: int = Field(default=4, description="梯度累积步数")
    
    # 评估
    eval_steps: int = Field(default=100, description="评估间隔步数")


class AppConfig(BaseSettings):
    """应用主配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 项目路径
    project_root: Path = Field(default=Path("."), description="项目根目录")
    output_dir: Path = Field(default=Path("output"), description="输出目录")
    templates_dir: Path = Field(default=Path("templates"), description="模板目录")
    
    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: Optional[Path] = Field(default=None, description="日志文件路径")
    
    # 子配置
    llm: LLMConfig = Field(default_factory=LLMConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)
    generator: GeneratorConfig = Field(default_factory=GeneratorConfig)
    processor: ProcessorConfig = Field(default_factory=ProcessorConfig)
    finetuning: FineTuningConfig = Field(default_factory=FineTuningConfig)
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "datasets").mkdir(exist_ok=True)
        (self.output_dir / "docs").mkdir(exist_ok=True)
        (self.output_dir / "models").mkdir(exist_ok=True)


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def load_config(env_file: Optional[str] = None) -> AppConfig:
    """加载配置"""
    global _config
    if env_file:
        _config = AppConfig(_env_file=env_file)
    else:
        _config = AppConfig()
    return _config

