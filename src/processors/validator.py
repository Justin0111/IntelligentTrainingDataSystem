"""
数据验证器模块
验证生成的训练数据的质量和完整性
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from ..config import get_config, ProcessorConfig
from ..generators.qa_generator import QAPair
from ..generators.design_generator import DesignProposal

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    ERROR = "error"      # 严重错误，数据无效
    WARNING = "warning"  # 警告，数据可能有问题
    INFO = "info"        # 信息，提示改进


@dataclass
class ValidationIssue:
    """验证问题"""
    level: ValidationLevel
    field: str
    message: str
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "field": self.field,
            "message": self.message,
            "suggestion": self.suggestion
        }


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    score: float = 1.0  # 质量分数 0-1
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "issues": [i.to_dict() for i in self.issues],
            "score": self.score
        }
    
    def add_issue(self, issue: ValidationIssue):
        """添加问题"""
        self.issues.append(issue)
        if issue.level == ValidationLevel.ERROR:
            self.is_valid = False


class DataValidator:
    """
    数据验证器
    
    验证问答对和设计方案数据的质量
    """
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """
        初始化验证器
        
        Args:
            config: 处理器配置
        """
        self.config = config or get_config().processor
    
    def validate_qa_pair(self, qa: QAPair) -> ValidationResult:
        """
        验证单个问答对
        
        Args:
            qa: 问答对数据
            
        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(is_valid=True, score=1.0)
        
        # 验证问题
        self._validate_question(qa.question, result)
        
        # 验证答案
        self._validate_answer(qa.answer, result)
        
        # 验证推理步骤
        self._validate_reasoning_trace(qa.reasoning_trace, result)
        
        # 验证代码上下文
        self._validate_code_context(qa.code_context, result)
        
        # 验证元数据
        self._validate_metadata(qa, result)
        
        # 计算质量分数
        result.score = self._calculate_qa_score(qa, result)
        
        return result
    
    def validate_design_proposal(self, design: DesignProposal) -> ValidationResult:
        """
        验证设计方案
        
        Args:
            design: 设计方案数据
            
        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(is_valid=True, score=1.0)
        
        # 验证需求描述
        if not design.requirement or len(design.requirement) < 5:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="requirement",
                message="需求描述为空或过短",
                suggestion="需求描述应清晰说明要实现的功能"
            ))
        
        # 验证概述
        if not design.overview or len(design.overview) < 20:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="overview",
                message="方案概述过短",
                suggestion="概述应包含方案的核心思路"
            ))
        
        # 验证组件
        if not design.components:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="components",
                message="缺少组件设计",
                suggestion="设计方案应包含至少一个组件"
            ))
        else:
            for i, comp in enumerate(design.components):
                if not comp.name:
                    result.add_issue(ValidationIssue(
                        level=ValidationLevel.ERROR,
                        field=f"components[{i}].name",
                        message="组件名称为空"
                    ))
                if not comp.responsibility:
                    result.add_issue(ValidationIssue(
                        level=ValidationLevel.WARNING,
                        field=f"components[{i}].responsibility",
                        message="组件职责描述为空",
                        suggestion="应说明组件的主要职责"
                    ))
        
        # 验证推理步骤
        self._validate_reasoning_trace(design.reasoning_trace, result)
        
        # 计算质量分数
        result.score = self._calculate_design_score(design, result)
        
        return result
    
    def _validate_question(self, question: str, result: ValidationResult):
        """验证问题"""
        # 检查长度
        if not question:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="question",
                message="问题为空"
            ))
            return
        
        if len(question) < self.config.min_question_length:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="question",
                message=f"问题过短（{len(question)} 字符，最少 {self.config.min_question_length}）",
                suggestion="问题应更具体和详细"
            ))
        
        # 检查是否包含问号（对于中英文）
        if not any(c in question for c in "?？"):
            result.add_issue(ValidationIssue(
                level=ValidationLevel.INFO,
                field="question",
                message="问题未以问号结尾",
                suggestion="建议添加问号以明确这是一个问题"
            ))
        
        # 检查是否过于通用
        generic_patterns = [
            r'^这是什么[？?]?$',
            r'^什么是.{1,5}[？?]?$',
            r'^how[？?]?$',
            r'^what[？?]?$'
        ]
        for pattern in generic_patterns:
            if re.match(pattern, question.lower().strip()):
                result.add_issue(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    field="question",
                    message="问题过于通用",
                    suggestion="问题应更具体，涉及代码的具体功能"
                ))
                break
    
    def _validate_answer(self, answer: str, result: ValidationResult):
        """验证答案"""
        if not answer:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="answer",
                message="答案为空"
            ))
            return
        
        if len(answer) < self.config.min_answer_length:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="answer",
                message=f"答案过短（{len(answer)} 字符，最少 {self.config.min_answer_length}）",
                suggestion="答案应更详细和完整"
            ))
        
        # 检查答案是否有实际内容
        if answer.strip() in ["无", "N/A", "TODO", "..."]:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="answer",
                message="答案没有实际内容"
            ))
        
        # 检查是否只是重复问题
        # 这里简化处理，检查相似度
    
    def _validate_reasoning_trace(
        self, 
        reasoning_trace: List, 
        result: ValidationResult
    ):
        """验证推理步骤"""
        if not reasoning_trace:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="reasoning_trace",
                message="缺少推理步骤",
                suggestion="应提供推理过程以增强可解释性"
            ))
            return
        
        min_steps = 2
        if len(reasoning_trace) < min_steps:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="reasoning_trace",
                message=f"推理步骤过少（{len(reasoning_trace)} 步，建议至少 {min_steps} 步）",
                suggestion="增加推理步骤以展示完整的思考过程"
            ))
        
        # 检查每个步骤
        for i, step in enumerate(reasoning_trace):
            thought = step.thought if hasattr(step, 'thought') else step.get('thought', '')
            if not thought or len(thought) < 5:
                result.add_issue(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    field=f"reasoning_trace[{i}]",
                    message="推理步骤内容过短"
                ))
    
    def _validate_code_context(self, code_context: Dict, result: ValidationResult):
        """验证代码上下文"""
        if not code_context:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="code_context",
                message="缺少代码上下文"
            ))
            return
        
        # 检查必要字段
        required_fields = ["file_path", "code_snippet"]
        for field in required_fields:
            if field not in code_context or not code_context[field]:
                result.add_issue(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    field=f"code_context.{field}",
                    message=f"缺少必要字段: {field}"
                ))
        
        # 检查代码片段
        code_snippet = code_context.get("code_snippet", "")
        if code_snippet and len(code_snippet) < 10:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="code_context.code_snippet",
                message="代码片段过短"
            ))
    
    def _validate_metadata(self, qa: QAPair, result: ValidationResult):
        """验证元数据"""
        # 检查 ID
        if not qa.id:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="id",
                message="缺少 ID"
            ))
        
        # 检查问题类型
        valid_types = [
            "function_explanation", "business_logic", "code_flow",
            "error_handling", "design_pattern", "api_usage", "general"
        ]
        if qa.question_type and qa.question_type not in valid_types:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.INFO,
                field="question_type",
                message=f"非标准问题类型: {qa.question_type}"
            ))
        
        # 检查难度级别
        valid_difficulties = ["easy", "medium", "hard"]
        if qa.difficulty and qa.difficulty not in valid_difficulties:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.INFO,
                field="difficulty",
                message=f"非标准难度级别: {qa.difficulty}"
            ))
    
    def _calculate_qa_score(self, qa: QAPair, result: ValidationResult) -> float:
        """计算问答对质量分数"""
        score = 1.0
        
        # 根据问题扣分
        error_count = sum(1 for i in result.issues if i.level == ValidationLevel.ERROR)
        warning_count = sum(1 for i in result.issues if i.level == ValidationLevel.WARNING)
        
        score -= error_count * 0.3
        score -= warning_count * 0.1
        
        # 加分项
        # 有文档字符串
        if qa.code_context.get("docstring"):
            score += 0.1
        
        # 有详细的推理步骤
        if len(qa.reasoning_trace) >= 3:
            score += 0.1
        
        # 有标签
        if qa.tags:
            score += 0.05
        
        # 有代码引用
        if qa.code_references:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _calculate_design_score(
        self, 
        design: DesignProposal, 
        result: ValidationResult
    ) -> float:
        """计算设计方案质量分数"""
        score = 1.0
        
        # 根据问题扣分
        error_count = sum(1 for i in result.issues if i.level == ValidationLevel.ERROR)
        warning_count = sum(1 for i in result.issues if i.level == ValidationLevel.WARNING)
        
        score -= error_count * 0.3
        score -= warning_count * 0.1
        
        # 加分项
        # 有多个组件
        if len(design.components) >= 2:
            score += 0.1
        
        # 有数据结构设计
        if design.data_structures:
            score += 0.1
        
        # 有集成点
        if design.integration_points:
            score += 0.1
        
        # 有设计模式
        if design.design_patterns_used:
            score += 0.1
        
        # 有权衡分析
        if design.trade_offs:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def validate_batch(
        self, 
        items: List[Any],
        item_type: str = "qa"
    ) -> Tuple[List[Any], List[Tuple[Any, ValidationResult]]]:
        """
        批量验证数据
        
        Args:
            items: 数据列表
            item_type: 数据类型 ("qa" 或 "design")
            
        Returns:
            (有效数据列表, 无效数据及其验证结果列表)
        """
        valid_items = []
        invalid_items = []
        
        for item in items:
            if item_type == "qa":
                result = self.validate_qa_pair(item)
            else:
                result = self.validate_design_proposal(item)
            
            if result.is_valid:
                valid_items.append(item)
            else:
                invalid_items.append((item, result))
        
        logger.info(
            f"验证完成: {len(valid_items)} 有效, {len(invalid_items)} 无效"
        )
        
        return valid_items, invalid_items
    
    def get_validation_report(
        self, 
        results: List[ValidationResult]
    ) -> Dict[str, Any]:
        """
        生成验证报告
        
        Args:
            results: 验证结果列表
            
        Returns:
            验证报告字典
        """
        total = len(results)
        valid_count = sum(1 for r in results if r.is_valid)
        avg_score = sum(r.score for r in results) / total if total > 0 else 0
        
        # 统计问题类型
        issue_counts = {
            "error": 0,
            "warning": 0,
            "info": 0
        }
        issue_fields = {}
        
        for result in results:
            for issue in result.issues:
                issue_counts[issue.level.value] += 1
                field = issue.field.split('[')[0]  # 移除数组索引
                issue_fields[field] = issue_fields.get(field, 0) + 1
        
        return {
            "total_items": total,
            "valid_items": valid_count,
            "invalid_items": total - valid_count,
            "validity_rate": valid_count / total if total > 0 else 0,
            "average_score": round(avg_score, 3),
            "issue_counts": issue_counts,
            "common_issues": dict(sorted(
                issue_fields.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10])
        }

