"""
数据清洗器模块
清洗和标准化训练数据
"""

import re
import hashlib
import logging
from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass

from ..config import get_config, ProcessorConfig
from ..generators.qa_generator import QAPair
from ..generators.design_generator import DesignProposal

logger = logging.getLogger(__name__)


@dataclass
class CleaningStats:
    """清洗统计"""
    total_input: int = 0
    duplicates_removed: int = 0
    whitespace_normalized: int = 0
    empty_removed: int = 0
    total_output: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "total_input": self.total_input,
            "duplicates_removed": self.duplicates_removed,
            "whitespace_normalized": self.whitespace_normalized,
            "empty_removed": self.empty_removed,
            "total_output": self.total_output
        }


class DataCleaner:
    """
    数据清洗器
    
    清洗、去重和标准化训练数据
    """
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """
        初始化清洗器
        
        Args:
            config: 处理器配置
        """
        self.config = config or get_config().processor
        self._seen_hashes: Set[str] = set()
    
    def clean_qa_pairs(self, qa_pairs: List[QAPair]) -> tuple[List[QAPair], CleaningStats]:
        """
        清洗问答对数据
        
        Args:
            qa_pairs: 问答对列表
            
        Returns:
            (清洗后的数据, 清洗统计)
        """
        stats = CleaningStats(total_input=len(qa_pairs))
        cleaned = []
        self._seen_hashes.clear()
        
        for qa in qa_pairs:
            # 清洗文本内容
            qa = self._clean_qa_text(qa, stats)
            
            # 跳过空数据
            if not qa.question or not qa.answer:
                stats.empty_removed += 1
                continue
            
            # 去重
            if self.config.remove_duplicates:
                content_hash = self._get_qa_hash(qa)
                if content_hash in self._seen_hashes:
                    stats.duplicates_removed += 1
                    continue
                self._seen_hashes.add(content_hash)
            
            cleaned.append(qa)
        
        stats.total_output = len(cleaned)
        logger.info(
            f"问答对清洗完成: {stats.total_input} -> {stats.total_output}, "
            f"去重 {stats.duplicates_removed}, 移除空数据 {stats.empty_removed}"
        )
        
        return cleaned, stats
    
    def clean_design_proposals(
        self, 
        designs: List[DesignProposal]
    ) -> tuple[List[DesignProposal], CleaningStats]:
        """
        清洗设计方案数据
        
        Args:
            designs: 设计方案列表
            
        Returns:
            (清洗后的数据, 清洗统计)
        """
        stats = CleaningStats(total_input=len(designs))
        cleaned = []
        self._seen_hashes.clear()
        
        for design in designs:
            # 清洗文本内容
            design = self._clean_design_text(design, stats)
            
            # 跳过空数据
            if not design.requirement or not design.overview:
                stats.empty_removed += 1
                continue
            
            # 去重
            if self.config.remove_duplicates:
                content_hash = self._get_design_hash(design)
                if content_hash in self._seen_hashes:
                    stats.duplicates_removed += 1
                    continue
                self._seen_hashes.add(content_hash)
            
            cleaned.append(design)
        
        stats.total_output = len(cleaned)
        logger.info(
            f"设计方案清洗完成: {stats.total_input} -> {stats.total_output}"
        )
        
        return cleaned, stats
    
    def _clean_qa_text(self, qa: QAPair, stats: CleaningStats) -> QAPair:
        """清洗问答对的文本内容"""
        modified = False
        
        # 清洗问题
        cleaned_question = self._normalize_text(qa.question)
        if cleaned_question != qa.question:
            qa.question = cleaned_question
            modified = True
        
        # 清洗答案
        cleaned_answer = self._normalize_text(qa.answer)
        if cleaned_answer != qa.answer:
            qa.answer = cleaned_answer
            modified = True
        
        # 清洗推理步骤
        for step in qa.reasoning_trace:
            cleaned_thought = self._normalize_text(step.thought)
            if cleaned_thought != step.thought:
                step.thought = cleaned_thought
                modified = True
        
        # 清洗代码上下文中的代码片段
        if "code_snippet" in qa.code_context:
            cleaned_code = self._clean_code(qa.code_context["code_snippet"])
            if cleaned_code != qa.code_context["code_snippet"]:
                qa.code_context["code_snippet"] = cleaned_code
                modified = True
        
        if modified:
            stats.whitespace_normalized += 1
        
        return qa
    
    def _clean_design_text(
        self, 
        design: DesignProposal, 
        stats: CleaningStats
    ) -> DesignProposal:
        """清洗设计方案的文本内容"""
        modified = False
        
        # 清洗需求
        cleaned_req = self._normalize_text(design.requirement)
        if cleaned_req != design.requirement:
            design.requirement = cleaned_req
            modified = True
        
        # 清洗概述
        cleaned_overview = self._normalize_text(design.overview)
        if cleaned_overview != design.overview:
            design.overview = cleaned_overview
            modified = True
        
        # 清洗组件描述
        for comp in design.components:
            cleaned_resp = self._normalize_text(comp.responsibility)
            if cleaned_resp != comp.responsibility:
                comp.responsibility = cleaned_resp
                modified = True
        
        # 清洗推理步骤
        for step in design.reasoning_trace:
            cleaned_thought = self._normalize_text(step.thought)
            if cleaned_thought != step.thought:
                step.thought = cleaned_thought
                modified = True
        
        if modified:
            stats.whitespace_normalized += 1
        
        return design
    
    def _normalize_text(self, text: str) -> str:
        """标准化文本"""
        if not text:
            return text
        
        if self.config.normalize_whitespace:
            # 移除多余空白字符
            text = re.sub(r'\s+', ' ', text)
            # 移除首尾空白
            text = text.strip()
            # 标准化换行符
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            # 移除连续的空行
            text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 移除不可见字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        return text
    
    def _clean_code(self, code: str) -> str:
        """清洗代码"""
        if not code:
            return code
        
        # 保留代码的缩进，但标准化空行
        lines = code.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            # 移除行尾空白
            line = line.rstrip()
            
            # 处理连续空行
            is_empty = not line.strip()
            if is_empty:
                if not prev_empty:
                    cleaned_lines.append('')
                prev_empty = True
            else:
                cleaned_lines.append(line)
                prev_empty = False
        
        # 移除首尾空行
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)
    
    def _get_qa_hash(self, qa: QAPair) -> str:
        """计算问答对的哈希值用于去重"""
        # 使用问题+答案的前100字符计算哈希
        content = f"{qa.question}|{qa.answer[:100]}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_design_hash(self, design: DesignProposal) -> str:
        """计算设计方案的哈希值用于去重"""
        # 使用需求+概述计算哈希
        content = f"{design.requirement}|{design.overview[:100]}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def remove_similar_qa(
        self, 
        qa_pairs: List[QAPair], 
        similarity_threshold: float = 0.8
    ) -> List[QAPair]:
        """
        移除相似度过高的问答对
        
        Args:
            qa_pairs: 问答对列表
            similarity_threshold: 相似度阈值
            
        Returns:
            去重后的问答对列表
        """
        if not qa_pairs:
            return qa_pairs
        
        unique_pairs = [qa_pairs[0]]
        
        for qa in qa_pairs[1:]:
            is_similar = False
            for existing in unique_pairs:
                # 简单的相似度计算：基于共同词比例
                sim = self._calculate_similarity(qa.question, existing.question)
                if sim >= similarity_threshold:
                    is_similar = True
                    break
            
            if not is_similar:
                unique_pairs.append(qa)
        
        removed = len(qa_pairs) - len(unique_pairs)
        if removed > 0:
            logger.info(f"移除了 {removed} 个相似问答对")
        
        return unique_pairs
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        # 简单的 Jaccard 相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def filter_by_quality(
        self, 
        qa_pairs: List[QAPair], 
        min_score: float = 0.5
    ) -> List[QAPair]:
        """
        根据质量分数过滤数据
        
        Args:
            qa_pairs: 问答对列表
            min_score: 最低质量分数
            
        Returns:
            过滤后的问答对列表
        """
        from .validator import DataValidator
        
        validator = DataValidator()
        filtered = []
        
        for qa in qa_pairs:
            result = validator.validate_qa_pair(qa)
            if result.score >= min_score:
                filtered.append(qa)
        
        removed = len(qa_pairs) - len(filtered)
        if removed > 0:
            logger.info(f"根据质量分数过滤了 {removed} 个问答对")
        
        return filtered
    
    def balance_dataset(
        self, 
        qa_pairs: List[QAPair],
        by_field: str = "question_type",
        max_per_category: Optional[int] = None
    ) -> List[QAPair]:
        """
        平衡数据集
        
        Args:
            qa_pairs: 问答对列表
            by_field: 平衡的字段
            max_per_category: 每个类别的最大数量
            
        Returns:
            平衡后的数据集
        """
        # 按类别分组
        categories: Dict[str, List[QAPair]] = {}
        
        for qa in qa_pairs:
            category = getattr(qa, by_field, "unknown")
            if category not in categories:
                categories[category] = []
            categories[category].append(qa)
        
        # 确定每个类别的数量
        if max_per_category is None:
            # 使用最小类别的数量
            max_per_category = min(len(items) for items in categories.values())
        
        # 平衡数据
        balanced = []
        for category, items in categories.items():
            balanced.extend(items[:max_per_category])
        
        logger.info(
            f"数据集平衡完成: {len(qa_pairs)} -> {len(balanced)}, "
            f"类别: {list(categories.keys())}"
        )
        
        return balanced

