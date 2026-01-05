"""
通用工具函数
"""

import json
import logging
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    设置日志配置
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        format_string: 日志格式字符串
        
    Returns:
        配置好的 logger 实例
    """
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    
    # 创建根 logger
    logger = logging.getLogger("training_data_generator")
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(logging.Formatter(format_string))
    logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(logging.Formatter(format_string))
        logger.addHandler(file_handler)
    
    return logger


def generate_id(prefix: str = "", content: Optional[str] = None) -> str:
    """
    生成唯一标识符
    
    Args:
        prefix: ID前缀
        content: 可选的内容，用于生成基于内容的哈希ID
        
    Returns:
        唯一标识符字符串
    """
    if content:
        # 基于内容生成哈希ID
        hash_obj = hashlib.md5(content.encode('utf-8'))
        hash_id = hash_obj.hexdigest()[:12]
        return f"{prefix}_{hash_id}" if prefix else hash_id
    else:
        # 生成随机UUID
        random_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{random_id}" if prefix else random_id


def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    加载 JSON 文件
    
    Args:
        file_path: JSON 文件路径
        
    Returns:
        解析后的字典
    """
    file_path = Path(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Union[Dict, List], file_path: Union[str, Path], indent: int = 2) -> None:
    """
    保存数据为 JSON 文件
    
    Args:
        data: 要保存的数据
        file_path: 目标文件路径
        indent: 缩进空格数
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def load_jsonl(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    加载 JSONL 文件
    
    Args:
        file_path: JSONL 文件路径
        
    Returns:
        字典列表
    """
    file_path = Path(file_path)
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def save_jsonl(data: List[Dict[str, Any]], file_path: Union[str, Path]) -> None:
    """
    保存数据为 JSONL 文件
    
    Args:
        data: 字典列表
        file_path: 目标文件路径
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def count_tokens_approx(text: str) -> int:
    """
    近似估计文本的 token 数量
    使用简单的字符/词估计方法
    
    Args:
        text: 输入文本
        
    Returns:
        估计的 token 数量
    """
    # 对于中文，大约每个字符1个token
    # 对于英文，大约每4个字符1个token
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    
    return chinese_chars + (other_chars // 4)


def get_file_extension(file_path: Union[str, Path]) -> str:
    """获取文件扩展名（小写）"""
    return Path(file_path).suffix.lower().lstrip('.')


def get_language_from_extension(extension: str) -> Optional[str]:
    """
    根据文件扩展名推断编程语言
    
    Args:
        extension: 文件扩展名
        
    Returns:
        编程语言名称，如果无法识别则返回 None
    """
    extension_map = {
        # Python
        'py': 'python',
        'pyw': 'python',
        'pyi': 'python',
        # JavaScript/TypeScript
        'js': 'javascript',
        'jsx': 'javascript',
        'ts': 'typescript',
        'tsx': 'typescript',
        'mjs': 'javascript',
        'cjs': 'javascript',
        # Java
        'java': 'java',
        # Go
        'go': 'go',
        # Rust
        'rs': 'rust',
        # C/C++
        'c': 'c',
        'h': 'c',
        'cpp': 'cpp',
        'cc': 'cpp',
        'cxx': 'cpp',
        'hpp': 'cpp',
        # Ruby
        'rb': 'ruby',
        # PHP
        'php': 'php',
        # Shell
        'sh': 'shell',
        'bash': 'shell',
        'zsh': 'shell',
        # Others
        'sql': 'sql',
        'r': 'r',
        'scala': 'scala',
        'kt': 'kotlin',
        'swift': 'swift',
    }
    return extension_map.get(extension.lower())


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """格式化时间戳"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def safe_dict_get(d: Dict, *keys, default=None):
    """安全地获取嵌套字典的值"""
    result = d
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result

