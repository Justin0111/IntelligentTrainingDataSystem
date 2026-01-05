"""
问答对生成器模块
场景1：根据本地代码仓的业务流程和规则，自动生成问答对
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..config import get_config, GeneratorConfig
from ..parsers.repo_scanner import RepoScanner, FileInfo
from ..parsers.ast_parser import get_parser_for_language, FunctionInfo, ClassInfo
from ..analyzers.logic_analyzer import LogicAnalyzer, LogicAnalysis
from .llm_client import LLMClient, QwenClient, PromptTemplate, create_llm_client
from ..utils.helpers import generate_id

logger = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    """推理步骤"""
    step: int
    thought: str
    
    def to_dict(self) -> Dict:
        return {"step": self.step, "thought": self.thought}


@dataclass
class CodeReference:
    """代码引用"""
    start_line: int
    end_line: int
    description: str
    
    def to_dict(self) -> Dict:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "description": self.description
        }


@dataclass
class QAPair:
    """问答对数据"""
    id: str
    question: str
    answer: str
    question_type: str
    code_context: Dict[str, Any]
    reasoning_trace: List[ReasoningStep]
    code_references: List[CodeReference] = field(default_factory=list)
    difficulty: str = "medium"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": "business_qa",
            "question": self.question,
            "answer": self.answer,
            "question_type": self.question_type,
            "code_context": self.code_context,
            "reasoning_trace": [r.to_dict() for r in self.reasoning_trace],
            "code_references": [r.to_dict() for r in self.code_references],
            "difficulty": self.difficulty,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at
        }
    
    def to_training_format(self) -> Dict:
        """转换为训练数据格式"""
        # 构建包含推理过程的回答
        reasoning_text = "\n".join([
            f"步骤{r.step}: {r.thought}" for r in self.reasoning_trace
        ])
        
        full_answer = f"""让我分析一下这个问题：

{reasoning_text}

综上所述：
{self.answer}

相关代码位置：{self.code_context.get('file_path', '')} 第{self.code_context.get('start_line', '')}-{self.code_context.get('end_line', '')}行"""
        
        return {
            "instruction": self.question,
            "input": f"代码上下文：\n```\n{self.code_context.get('code_snippet', '')}\n```",
            "output": full_answer
        }


class QAGenerator:
    """
    问答对生成器
    
    分析代码文件并生成高质量的问答对数据
    """
    
    # 问题类型模板
    QUESTION_TEMPLATES = {
        "function_explanation": [
            "这个函数 {func_name} 的主要功能是什么？",
            "{func_name} 函数是如何实现的？请详细解释。",
            "请解释 {func_name} 函数的工作原理。",
        ],
        "business_logic": [
            "这段代码实现了什么业务逻辑？",
            "这个模块的业务规则是什么？",
            "{func_name} 中的业务处理流程是怎样的？",
        ],
        "code_flow": [
            "这个函数的执行流程是什么？",
            "数据在 {func_name} 中是如何流转的？",
            "请描述 {func_name} 的控制流程。",
        ],
        "error_handling": [
            "这段代码如何处理异常情况？",
            "{func_name} 的错误处理机制是什么？",
            "如果输入无效，这个函数会如何响应？",
        ],
        "design_pattern": [
            "这段代码使用了什么设计模式？",
            "{class_name} 类的设计思想是什么？",
            "这个模块的架构设计有什么特点？",
        ],
        "api_usage": [
            "如何使用 {func_name} 函数？",
            "调用 {func_name} 需要传入什么参数？",
            "{func_name} 的返回值是什么？",
        ]
    }
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        config: Optional[GeneratorConfig] = None
    ):
        """
        初始化问答对生成器
        
        Args:
            llm_client: LLM 客户端
            config: 生成器配置
        """
        self.config = config or get_config().generator
        self.llm_client = llm_client or create_llm_client()
        self.prompt_template = PromptTemplate()
        self.logic_analyzer = LogicAnalyzer()
        self.scanner = RepoScanner()
    
    def _sanitize_code(self, code: str) -> str:
        """清理代码中可能的敏感信息"""
        import re
        
        # 替换常见的敏感信息模式
        # API keys, tokens, passwords等
        patterns = [
            (r'(api[_-]?key|token|password|secret|auth)["\']?\s*[:=]\s*["\']([^"\']+)["\']', 
             r'\1="***REDACTED***"'),
            (r'(sk-[a-zA-Z0-9]{32,})', r'sk-***REDACTED***'),  # OpenAI API keys
            (r'([a-f0-9]{32,64})', lambda m: m.group(1)[:8] + '***' if len(m.group(1)) > 16 else m.group(1)),  # 长哈希值
        ]
        
        sanitized = code
        for pattern, replacement in patterns:
            if callable(replacement):
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            else:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        # 限制代码长度，避免过长
        max_length = 2000  # 字符
        if len(sanitized) > max_length:
            # 保留开头和结尾
            half = max_length // 2
            sanitized = sanitized[:half] + "\n... (代码已截断) ...\n" + sanitized[-half:]
        
        return sanitized
    
    def generate_for_file(
        self,
        file_path: Path,
        code: str,
        language: str,
        num_qa: Optional[int] = None
    ) -> List[QAPair]:
        """
        为单个文件生成问答对
        
        Args:
            file_path: 文件路径
            code: 源代码
            language: 编程语言
            num_qa: 生成的问答对数量
            
        Returns:
            问答对列表
        """
        num_qa = num_qa or self.config.qa_per_file
        qa_pairs = []
        
        # 解析代码
        parser = get_parser_for_language(language)
        if not parser:
            logger.warning(f"不支持的语言: {language}")
            return qa_pairs
        
        try:
            parse_result = parser.parse(code, str(file_path))
        except Exception as e:
            logger.error(f"解析失败: {file_path}, 错误: {e}")
            return qa_pairs
        
        # 分析业务逻辑
        logic_analysis = self.logic_analyzer.analyze_file(code, str(file_path), language)
        
        # 获取所有函数
        all_functions = parse_result.get_all_functions()
        
        # 选择要生成问答的函数（优先选择关键函数）
        key_functions = self._select_key_functions(all_functions, logic_analysis)
        
        # 为每个选中的函数生成问答对
        for func in key_functions[:num_qa]:
            try:
                qa = self._generate_qa_for_function(
                    func, file_path, code, language, logic_analysis
                )
                if qa:
                    qa_pairs.extend(qa)
            except Exception as e:
                logger.warning(f"生成问答失败: {func.name}, 错误: {e}")
        
        # 为类生成问答
        for cls in parse_result.classes[:2]:
            try:
                qa = self._generate_qa_for_class(
                    cls, file_path, code, language
                )
                if qa:
                    qa_pairs.append(qa)
            except Exception as e:
                logger.warning(f"生成类问答失败: {cls.name}, 错误: {e}")
        
        logger.info(f"为文件 {file_path} 生成了 {len(qa_pairs)} 个问答对")
        return qa_pairs
    
    def _select_key_functions(
        self,
        functions: List[FunctionInfo],
        logic_analysis: LogicAnalysis
    ) -> List[FunctionInfo]:
        """选择关键函数用于生成问答"""
        # 按重要性评分
        scored_functions = []
        key_func_names = {f.name for f in logic_analysis.key_functions}
        
        for func in functions:
            score = 0
            
            # 是否是关键函数
            if func.name in key_func_names:
                score += 5
            
            # 有文档字符串
            if func.docstring:
                score += 2
            
            # 复杂度
            score += min(func.complexity, 5)
            
            # 代码长度适中
            lines = len(func.code.split('\n'))
            if 5 <= lines <= 50:
                score += 2
            
            # 不是私有方法
            if not func.name.startswith('_'):
                score += 1
            
            scored_functions.append((score, func))
        
        # 按分数排序
        scored_functions.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored_functions]
    
    def _generate_qa_for_function(
        self,
        func: FunctionInfo,
        file_path: Path,
        code: str,
        language: str,
        logic_analysis: LogicAnalysis
    ) -> List[QAPair]:
        """为函数生成问答对"""
        qa_pairs = []
        
        # 准备代码上下文
        code_context = {
            "file_path": str(file_path),
            "start_line": func.start_line,
            "end_line": func.end_line,
            "code_snippet": func.code,
            "function_name": func.name,
            "parameters": func.parameters,
            "return_type": func.return_type
        }
        
        # 准备附加上下文
        additional_context = ""
        if func.docstring:
            additional_context += f"函数文档: {func.docstring}\n"
        
        # 查找相关的业务规则
        related_rules = [
            r for r in logic_analysis.business_rules 
            if r.name == func.name
        ]
        if related_rules:
            additional_context += f"业务规则: {related_rules[0].description}\n"
        
        # 使用 LLM 生成问答
        try:
            # 检查代码片段是否可能包含敏感内容
            code_snippet = func.code
            if get_config().llm.sanitize_code:
                code_snippet = self._sanitize_code(func.code)
            
            prompt = self.prompt_template.render(
                "qa_prompt",
                file_path=str(file_path),
                language=language,
                module_name=file_path.parent.name,
                code_snippet=code_snippet,
                additional_context=additional_context,
                num_qa=2  # 每个函数生成2个问答
            )
            
            response = self.llm_client.generate_with_json(prompt)
            
            # 解析响应
            if isinstance(response, list):
                for item in response:
                    qa = self._parse_qa_response(item, code_context, file_path, language)
                    if qa:
                        qa_pairs.append(qa)
            elif isinstance(response, dict):
                qa = self._parse_qa_response(response, code_context, file_path, language)
                if qa:
                    qa_pairs.append(qa)
            
            # 如果 LLM 没有生成任何有效的问答，使用模板
            if not qa_pairs:
                logger.info(f"LLM 未生成有效问答，使用模板: {func.name}")
                qa = self._generate_template_qa(func, code_context, file_path, language)
                if qa:
                    qa_pairs.append(qa)
                    
        except ValueError as e:
            # JSON 解析失败或内容审核失败
            error_msg = str(e)
            if "内容审核失败" in error_msg:
                logger.warning(f"内容审核失败（{func.name}），跳过此函数")
                # 内容审核失败，不生成问答对
                return []
            else:
                logger.warning(f"LLM 生成失败: {e}")
                # 使用模板生成备用问答
                qa = self._generate_template_qa(func, code_context, file_path, language)
                if qa:
                    qa_pairs.append(qa)
        except Exception as e:
            logger.warning(f"LLM 生成失败: {e}")
            # 使用模板生成备用问答
            qa = self._generate_template_qa(func, code_context, file_path, language)
            if qa:
                qa_pairs.append(qa)
        
        return qa_pairs
    
    def _parse_qa_response(
        self,
        response: Dict,
        code_context: Dict,
        file_path: Path,
        language: str
    ) -> Optional[QAPair]:
        """解析 LLM 响应为 QAPair"""
        try:
            # 解析推理步骤
            reasoning_trace = []
            raw_trace = response.get("reasoning_trace", [])
            for item in raw_trace:
                if isinstance(item, dict):
                    reasoning_trace.append(ReasoningStep(
                        step=item.get("step", len(reasoning_trace) + 1),
                        thought=item.get("thought", "")
                    ))
            
            # 解析代码引用
            code_references = []
            raw_refs = response.get("code_references", [])
            for ref in raw_refs:
                if isinstance(ref, dict):
                    code_references.append(CodeReference(
                        start_line=ref.get("start_line", 0),
                        end_line=ref.get("end_line", 0),
                        description=ref.get("description", "")
                    ))
            
            return QAPair(
                id=generate_id("qa"),
                question=response.get("question", ""),
                answer=response.get("answer", ""),
                question_type=response.get("question_type", "general"),
                code_context=code_context,
                reasoning_trace=reasoning_trace,
                code_references=code_references,
                difficulty=response.get("difficulty", "medium"),
                tags=response.get("tags", []),
                metadata={
                    "file_path": str(file_path),
                    "language": language,
                    "generated_by": "llm"
                }
            )
        except Exception as e:
            logger.warning(f"解析响应失败: {e}")
            return None
    
    def _generate_template_qa(
        self,
        func: FunctionInfo,
        code_context: Dict,
        file_path: Path,
        language: str
    ) -> Optional[QAPair]:
        """使用模板生成备用问答"""
        # 选择问题类型
        if "validate" in func.name.lower() or "check" in func.name.lower():
            q_type = "business_logic"
        elif func.complexity > 3:
            q_type = "code_flow"
        else:
            q_type = "function_explanation"
        
        # 生成问题
        templates = self.QUESTION_TEMPLATES.get(q_type, self.QUESTION_TEMPLATES["function_explanation"])
        question = templates[0].format(func_name=func.name, class_name=func.parent or "")
        
        # 生成答案
        answer = func.docstring or f"函数 {func.name} "
        if func.parameters:
            params = ", ".join([p.get("name", "") for p in func.parameters])
            answer += f"接受参数 ({params})"
        if func.return_type:
            answer += f"，返回类型为 {func.return_type}"
        
        # 生成推理步骤
        reasoning_trace = [
            ReasoningStep(1, f"首先，我需要理解 {func.name} 函数的定义和参数"),
            ReasoningStep(2, f"然后，分析函数体中的主要逻辑"),
            ReasoningStep(3, "最后，总结函数的功能和用途")
        ]
        
        return QAPair(
            id=generate_id("qa"),
            question=question,
            answer=answer,
            question_type=q_type,
            code_context=code_context,
            reasoning_trace=reasoning_trace,
            difficulty="easy",
            tags=[language, q_type],
            metadata={
                "file_path": str(file_path),
                "language": language,
                "generated_by": "template"
            }
        )
    
    def _generate_qa_for_class(
        self,
        cls: ClassInfo,
        file_path: Path,
        code: str,
        language: str
    ) -> Optional[QAPair]:
        """为类生成问答对"""
        code_context = {
            "file_path": str(file_path),
            "start_line": cls.start_line,
            "end_line": cls.end_line,
            "code_snippet": cls.code[:500] + "..." if len(cls.code) > 500 else cls.code,
            "class_name": cls.name,
            "bases": cls.bases,
            "methods": [m.name for m in cls.methods]
        }
        
        question = f"请解释 {cls.name} 类的设计和职责。"
        
        # 构建答案
        answer_parts = [f"{cls.name} 类"]
        if cls.bases:
            answer_parts.append(f"继承自 {', '.join(cls.bases)}")
        if cls.docstring:
            answer_parts.append(f"。{cls.docstring}")
        if cls.methods:
            answer_parts.append(f"主要方法包括: {', '.join([m.name for m in cls.methods[:5]])}")
        
        answer = ''.join(answer_parts)
        
        reasoning_trace = [
            ReasoningStep(1, f"分析类 {cls.name} 的定义和继承关系"),
            ReasoningStep(2, "查看类的属性和方法"),
            ReasoningStep(3, "理解类的职责和设计意图")
        ]
        
        return QAPair(
            id=generate_id("qa"),
            question=question,
            answer=answer,
            question_type="design_pattern",
            code_context=code_context,
            reasoning_trace=reasoning_trace,
            difficulty="medium",
            tags=[language, "class", "design"],
            metadata={
                "file_path": str(file_path),
                "language": language,
                "generated_by": "template"
            }
        )
    
    def generate_for_repository(
        self,
        repo_path: Path,
        max_files: int = 50,
        languages: Optional[List[str]] = None
    ) -> List[QAPair]:
        """
        为整个仓库生成问答对
        
        Args:
            repo_path: 仓库路径
            max_files: 最大处理文件数
            languages: 要处理的语言列表
            
        Returns:
            所有问答对列表
        """
        repo_path = Path(repo_path).resolve()
        all_qa_pairs = []
        
        # 扫描仓库
        repo_info = self.scanner.scan_repository(repo_path, load_content=True)
        
        # 过滤文件
        files_to_process = []
        for file_info in repo_info.files:
            if file_info.language and file_info.content:
                if languages is None or file_info.language in languages:
                    files_to_process.append(file_info)
        
        # 限制文件数量
        files_to_process = files_to_process[:max_files]
        
        logger.info(f"准备处理 {len(files_to_process)} 个文件")
        
        # 处理每个文件
        for file_info in files_to_process:
            try:
                qa_pairs = self.generate_for_file(
                    Path(file_info.relative_path),
                    file_info.content,
                    file_info.language
                )
                all_qa_pairs.extend(qa_pairs)
            except Exception as e:
                logger.error(f"处理文件失败: {file_info.relative_path}, 错误: {e}")
        
        logger.info(f"总共生成 {len(all_qa_pairs)} 个问答对")
        return all_qa_pairs

