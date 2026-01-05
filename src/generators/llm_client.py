"""
LLM 客户端模块
提供统一的 LLM API 调用接口，支持多种后端
"""

import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Generator
from dataclasses import dataclass
from pathlib import Path

from ..config import get_config, LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM 响应结果"""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    raw_response: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage,
            "finish_reason": self.finish_reason
        }


class LLMClient(ABC):
    """LLM 客户端抽象基类"""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        生成文本
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            LLMResponse 响应结果
        """
        pass
    
    @abstractmethod
    def generate_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成 JSON 格式的响应
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            
        Returns:
            解析后的 JSON 对象
        """
        pass


class QwenClient(LLMClient):
    """
    阿里云通义千问 API 客户端
    
    使用 DashScope SDK 调用 Qwen 模型
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 Qwen 客户端
        
        Args:
            config: LLM 配置
        """
        self.config = config or get_config().llm
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """初始化 DashScope 客户端"""
        try:
            import dashscope
            import os
            
            # 优先使用配置中的 API key，如果没有则从环境变量读取
            api_key = self.config.api_key
            if not api_key:
                api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("LLM_API_KEY")
            
            if api_key:
                dashscope.api_key = api_key
                logger.info(f"Qwen 客户端初始化成功，模型: {self.config.model_name}")
            else:
                logger.warning("未找到 API key，请设置 LLM_API_KEY 或 DASHSCOPE_API_KEY 环境变量")
            
            self._client = dashscope
        except ImportError:
            logger.warning("dashscope 未安装，请运行: pip install dashscope")
            self._client = None
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """调用 Qwen API 生成文本"""
        if not self._client:
            raise RuntimeError("DashScope 客户端未初始化")
        
        from dashscope import Generation
        import os
        
        # 确保 API key 在每次调用时都被设置
        api_key = self.config.api_key
        if not api_key:
            api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("LLM_API_KEY")
        
        if not api_key:
            raise ValueError(
                "未找到 API key。请设置 LLM_API_KEY 或 DASHSCOPE_API_KEY 环境变量，"
                "或在 .env 文件中配置 LLM_API_KEY。"
            )
        
        # 设置 API key
        Generation.api_key = api_key
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # 使用配置或参数值
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens
        
        # 重试逻辑
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = Generation.call(
                    model=self.config.model_name,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tok,
                    result_format='message',
                    **kwargs
                )
                
                if response.status_code == 200:
                    output = response.output
                    return LLMResponse(
                        content=output.choices[0].message.content,
                        model=self.config.model_name,
                        usage={
                            "prompt_tokens": response.usage.input_tokens,
                            "completion_tokens": response.usage.output_tokens,
                            "total_tokens": response.usage.total_tokens
                        },
                        finish_reason=output.choices[0].finish_reason,
                        raw_response=response
                    )
                else:
                    error_msg = response.message if hasattr(response, 'message') else str(response)
                    error_code = response.code if hasattr(response, 'code') else response.status_code
                    
                    # 针对 API key 错误提供更详细的提示
                    if error_code == "InvalidApiKey" or "Invalid API-key" in error_msg:
                        last_error = (
                            f"API 错误: {error_code} - {error_msg}\n"
                            f"提示: 请检查 .env 文件中的 LLM_API_KEY 是否正确，"
                            f"或访问 https://dashscope.console.aliyun.com/ 获取有效的 API key。"
                        )
                    # 针对内容审核失败
                    elif error_code == "DataInspectionFailed" or "inappropriate content" in error_msg.lower():
                        last_error = f"API 错误: {error_code} - 内容审核失败（可能包含敏感内容）"
                        logger.warning(f"尝试 {attempt + 1}/{self.config.max_retries}: {last_error}")
                        # 内容审核失败不需要重试，直接抛出
                        raise ValueError(
                            f"内容审核失败: 输入内容可能包含敏感信息。"
                            f"请尝试清理代码中的敏感数据（如密钥、密码等）后重试。"
                        )
                    else:
                        last_error = f"API 错误: {error_code} - {error_msg}"
                    logger.warning(f"尝试 {attempt + 1}/{self.config.max_retries}: {last_error}")
                    
            except Exception as e:
                last_error = str(e)
                # 检查是否是 API key 相关错误
                if "InvalidApiKey" in str(e) or "Invalid API-key" in str(e) or "401" in str(e):
                    last_error = (
                        f"{str(e)}\n"
                        f"提示: API key 无效。请检查 .env 文件中的 LLM_API_KEY 是否正确，"
                        f"或访问 https://dashscope.console.aliyun.com/ 获取有效的 API key。"
                    )
                logger.warning(f"尝试 {attempt + 1}/{self.config.max_retries}: {last_error}")
            
            # 指数退避
            if attempt < self.config.max_retries - 1:
                time.sleep(2 ** attempt)
        
        raise RuntimeError(f"API 调用失败，已重试 {self.config.max_retries} 次: {last_error}")
    
    def generate_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成 JSON 格式响应"""
        # 添加 JSON 格式要求到系统提示
        json_system = system_prompt or ""
        json_system += "\n\n请确保你的回复是有效的 JSON 格式，不要包含其他文字。所有字符串中的换行符必须使用 \\n 转义。"
        
        response = self.generate(prompt, json_system, **kwargs)
        
        # 解析 JSON
        content = response.content.strip()
        original_content = content  # 保存原始内容用于调试
        
        # 尝试提取 JSON 块
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end == -1:
                # 如果没有找到结束标记，尝试找到文件末尾
                content = content[start:].strip()
            else:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end == -1:
                content = content[start:].strip()
            else:
                content = content[start:end].strip()
        
        # 尝试多次修复和解析
        parse_attempts = [
            ("原始内容", content),
            ("基础修复", lambda: self._fix_json_format(content)),
            ("激进修复", lambda: self._aggressive_json_fix(content)),
            ("完全重建", lambda: self._rebuild_json(content)),
        ]
        
        last_error = None
        for attempt_name, get_content in parse_attempts:
            try:
                if callable(get_content):
                    test_content = get_content()
                else:
                    test_content = get_content
                
                result = json.loads(test_content)
                if attempt_name != "原始内容":
                    logger.info(f"JSON 解析成功（使用 {attempt_name}）")
                return result
                
            except json.JSONDecodeError as e:
                last_error = e
                logger.debug(f"{attempt_name} 解析失败: {e}")
                if attempt_name == "原始内容":
                    # 只在第一次失败时输出详细信息
                    logger.debug(f"错误位置: line {e.lineno}, column {e.colno}")
                    # 输出错误位置附近的内容
                    lines = test_content.split('\n')
                    if 0 < e.lineno <= len(lines):
                        error_line = lines[e.lineno - 1]
                        logger.debug(f"错误行内容: {error_line}")
                        if e.colno > 0:
                            logger.debug(f"错误位置: {' ' * (e.colno - 1)}^")
                continue
            except Exception as e:
                logger.debug(f"{attempt_name} 处理失败: {e}")
                continue
        
        # 所有尝试都失败了，输出完整内容用于调试
        logger.error("所有 JSON 解析尝试都失败")
        logger.error(f"完整内容:\n{original_content}")
        raise ValueError(f"无法解析 JSON 响应: {last_error}")
    
    def _fix_json_format(self, content: str) -> str:
        """修复常见的 JSON 格式问题"""
        import re
        
        # 移除 BOM 标记
        if content.startswith('\ufeff'):
            content = content[1:]
        
        # 移除开头的非JSON字符（如说明文字）
        first_bracket = -1
        for i, char in enumerate(content):
            if char in '[{':
                first_bracket = i
                break
        
        if first_bracket > 0 and first_bracket < 50:
            content = content[first_bracket:]
        
        # 移除尾部的非JSON字符
        last_bracket = -1
        for i in range(len(content) - 1, -1, -1):
            if content[i] in ']}':
                last_bracket = i
                break
        
        if last_bracket > 0 and last_bracket < len(content) - 1:
            content = content[:last_bracket + 1]
        
        # 修复多行字符串问题：将键值之间的换行移除
        # "key": \n"value" -> "key": "value"
        content = re.sub(r'"\s*:\s*\n\s*"', '": "', content)
        
        # 修复字符串值中的未转义换行符
        # 使用状态机方法，更可靠
        result = []
        in_string = False
        in_key = False
        escape_next = False
        i = 0
        
        while i < len(content):
            char = content[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                result.append(char)
                escape_next = True
                i += 1
                continue
            
            if char == '"':
                # 检查是否是键还是值
                if not in_string:
                    # 开始字符串
                    # 向后查找，看是否是键（后面跟冒号）
                    j = i + 1
                    while j < len(content) and content[j] != '"':
                        if content[j] == '\\':
                            j += 2
                        else:
                            j += 1
                    # 跳过字符串后的空白
                    k = j + 1
                    while k < len(content) and content[k] in ' \t\n\r':
                        k += 1
                    in_key = (k < len(content) and content[k] == ':')
                    in_string = True
                else:
                    # 结束字符串
                    in_string = False
                    in_key = False
                result.append(char)
                i += 1
                continue
            
            # 如果在字符串值中遇到换行符，转义它
            if in_string and not in_key and char in '\n\r':
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    # 检查是否是 \r\n
                    if i + 1 < len(content) and content[i + 1] == '\n':
                        result.append('\\n')
                        i += 2  # 跳过 \r\n
                        continue
                    else:
                        result.append('\\n')
                i += 1
                continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    def _aggressive_json_fix(self, content: str) -> str:
        """更激进的 JSON 修复策略"""
        import re
        
        # 先应用基础修复
        content = self._fix_json_format(content)
        
        # 移除尾随逗号
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        
        # 修复缺失的逗号（两个连续的对象/数组元素之间）
        # "key1": "value1" \n "key2": "value2" -> "key1": "value1", \n "key2": "value2"
        content = re.sub(r'"\s*\n\s*"', '",\n"', content)
        content = re.sub(r'}\s*\n\s*{', '},\n{', content)
        content = re.sub(r']\s*\n\s*\[', '],\n[', content)
        
        # 修复缺失的引号
        # key: "value" -> "key": "value"
        content = re.sub(r'(\n\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        
        return content
    
    def _rebuild_json(self, content: str) -> str:
        """完全重建 JSON - 最后的尝试"""
        import re
        
        # 尝试提取所有看起来像 JSON 键值对的内容
        # 这是最后的尝试，会尽可能宽松地解析
        
        # 移除所有控制字符（除了必要的）
        content = ''.join(char if ord(char) >= 32 or char in '\n\r\t' else ' ' for char in content)
        
        # 应用所有已知的修复
        content = self._aggressive_json_fix(content)
        
        # 如果仍然有问题，尝试手动提取键值对并重建
        try:
            # 检查是否是数组还是对象
            content = content.strip()
            if content.startswith('['):
                # 数组格式
                # 尝试找到所有的对象
                objects = []
                depth = 0
                current_obj = []
                
                for char in content:
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                    
                    current_obj.append(char)
                    
                    if depth == 0 and len(current_obj) > 1 and current_obj[-1] == '}':
                        # 找到一个完整的对象
                        obj_str = ''.join(current_obj).strip()
                        if obj_str.startswith(','):
                            obj_str = obj_str[1:].strip()
                        objects.append(obj_str)
                        current_obj = []
                
                if objects:
                    # 重建数组
                    return '[' + ','.join(objects) + ']'
        except:
            pass
        
        return content


class MockLLMClient(LLMClient):
    """
    模拟 LLM 客户端（用于测试）
    """
    
    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = responses or ["这是一个模拟响应"]
        self.call_count = 0
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        
        return LLMResponse(
            content=response_text,
            model="mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            finish_reason="stop"
        )
    
    def generate_with_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        response = self.generate(prompt, system_prompt, **kwargs)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"mock": True, "content": response.content}


class PromptTemplate:
    """
    Prompt 模板管理器
    
    支持从文件加载和变量替换
    """
    
    def __init__(self, template_dir: Optional[Path] = None):
        """
        初始化模板管理器
        
        Args:
            template_dir: 模板目录路径
        """
        self.template_dir = template_dir or Path("templates")
        self._cache: Dict[str, str] = {}
    
    def load(self, template_name: str) -> str:
        """
        加载模板
        
        Args:
            template_name: 模板名称（不含扩展名）
            
        Returns:
            模板内容
        """
        if template_name in self._cache:
            return self._cache[template_name]
        
        # 尝试不同的扩展名
        for ext in [".txt", ".md", ".prompt", ""]:
            template_path = self.template_dir / f"{template_name}{ext}"
            if template_path.exists():
                content = template_path.read_text(encoding='utf-8')
                self._cache[template_name] = content
                return content
        
        raise FileNotFoundError(f"模板未找到: {template_name}")
    
    def render(self, template_name: str, **variables) -> str:
        """
        渲染模板
        
        Args:
            template_name: 模板名称
            **variables: 模板变量
            
        Returns:
            渲染后的内容
        """
        template = self.load(template_name)
        
        # 简单的变量替换
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            template = template.replace(placeholder, str(value))
        
        return template
    
    def render_string(self, template_str: str, **variables) -> str:
        """
        渲染模板字符串
        
        Args:
            template_str: 模板字符串
            **variables: 模板变量
            
        Returns:
            渲染后的内容
        """
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            template_str = template_str.replace(placeholder, str(value))
        
        return template_str


# 工厂函数
def create_llm_client(provider: Optional[str] = None) -> LLMClient:
    """
    创建 LLM 客户端
    
    Args:
        provider: 提供商名称 (qwen, openai, mock)
        
    Returns:
        LLM 客户端实例
    """
    config = get_config().llm
    provider = provider or config.provider
    
    if provider == "qwen":
        return QwenClient(config)
    elif provider == "mock":
        return MockLLMClient()
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")

