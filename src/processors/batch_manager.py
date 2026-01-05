"""
批量处理管理器
处理多个代码仓库并生成统一的训练数据集
"""

import json
import logging
import random
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict

from ..generators.qa_generator import QAPair
from ..generators.design_generator import DesignProposal
from ..utils.helpers import save_json, save_jsonl

logger = logging.getLogger(__name__)


@dataclass
class RepoDataStats:
    """单个仓库的数据统计"""
    repo_name: str
    repo_path: str
    qa_count: int
    design_count: int
    languages: Dict[str, int]
    processing_time: float
    errors: List[str]


@dataclass
class BatchStats:
    """批处理统计信息"""
    total_repos: int
    successful_repos: int
    failed_repos: int
    total_qa_pairs: int
    total_designs: int
    repo_stats: List[RepoDataStats]
    start_time: str
    end_time: str
    duration_seconds: float


class BatchDataBalancer:
    """
    数据平衡器
    确保来自不同仓库的数据分布均衡
    """
    
    def __init__(
        self,
        max_qa_per_repo: Optional[int] = None,
        max_design_per_repo: Optional[int] = None,
        balance_strategy: str = "proportional"
    ):
        """
        初始化数据平衡器
        
        Args:
            max_qa_per_repo: 每个仓库最大QA数量
            max_design_per_repo: 每个仓库最大设计方案数量
            balance_strategy: 平衡策略 ("proportional", "uniform", "weighted")
        """
        self.max_qa_per_repo = max_qa_per_repo
        self.max_design_per_repo = max_design_per_repo
        self.balance_strategy = balance_strategy
    
    def balance_qa_data(
        self,
        repo_qa_map: Dict[str, List[QAPair]]
    ) -> Dict[str, List[QAPair]]:
        """
        平衡问答对数据
        
        Args:
            repo_qa_map: 仓库名 -> QA列表的映射
            
        Returns:
            平衡后的数据映射
        """
        if self.balance_strategy == "uniform":
            return self._balance_uniform(repo_qa_map, self.max_qa_per_repo)
        elif self.balance_strategy == "weighted":
            return self._balance_weighted(repo_qa_map, self.max_qa_per_repo)
        else:  # proportional (default)
            return self._balance_proportional(repo_qa_map, self.max_qa_per_repo)
    
    def balance_design_data(
        self,
        repo_design_map: Dict[str, List[DesignProposal]]
    ) -> Dict[str, List[DesignProposal]]:
        """
        平衡设计方案数据
        
        Args:
            repo_design_map: 仓库名 -> 设计方案列表的映射
            
        Returns:
            平衡后的数据映射
        """
        if self.balance_strategy == "uniform":
            return self._balance_uniform(repo_design_map, self.max_design_per_repo)
        elif self.balance_strategy == "weighted":
            return self._balance_weighted(repo_design_map, self.max_design_per_repo)
        else:  # proportional
            return self._balance_proportional(repo_design_map, self.max_design_per_repo)
    
    def _balance_uniform(
        self,
        data_map: Dict[str, List],
        max_per_repo: Optional[int]
    ) -> Dict[str, List]:
        """
        均匀平衡策略：每个仓库贡献相同数量的数据
        """
        if not data_map:
            return {}
        
        # 找到最小的数据量
        min_count = min(len(items) for items in data_map.values())
        
        if max_per_repo:
            target_count = min(min_count, max_per_repo)
        else:
            target_count = min_count
        
        balanced = {}
        for repo_name, items in data_map.items():
            if len(items) > target_count:
                # 随机抽样
                balanced[repo_name] = random.sample(items, target_count)
                logger.info(f"[{repo_name}] 均匀平衡: {len(items)} -> {target_count}")
            else:
                balanced[repo_name] = items
        
        return balanced
    
    def _balance_proportional(
        self,
        data_map: Dict[str, List],
        max_per_repo: Optional[int]
    ) -> Dict[str, List]:
        """
        比例平衡策略：按比例限制每个仓库，但保持相对比例
        """
        balanced = {}
        for repo_name, items in data_map.items():
            if max_per_repo and len(items) > max_per_repo:
                # 随机抽样到最大值
                balanced[repo_name] = random.sample(items, max_per_repo)
                logger.info(f"[{repo_name}] 比例平衡: {len(items)} -> {max_per_repo}")
            else:
                balanced[repo_name] = items
        
        return balanced
    
    def _balance_weighted(
        self,
        data_map: Dict[str, List],
        max_per_repo: Optional[int]
    ) -> Dict[str, List]:
        """
        加权平衡策略：根据数据质量评分加权
        暂时使用比例策略的简化版本
        """
        # TODO: 实现基于质量评分的加权平衡
        return self._balance_proportional(data_map, max_per_repo)


class BatchDataMerger:
    """
    数据合并器
    合并多个仓库的数据并生成统一数据集
    """
    
    def __init__(self, shuffle: bool = True, deduplicate: bool = True):
        """
        初始化数据合并器
        
        Args:
            shuffle: 是否打乱数据
            deduplicate: 是否去重
        """
        self.shuffle = shuffle
        self.deduplicate = deduplicate
    
    def merge_qa_data(
        self,
        repo_qa_map: Dict[str, List[QAPair]]
    ) -> Tuple[List[QAPair], Dict[str, Any]]:
        """
        合并问答对数据
        
        Args:
            repo_qa_map: 仓库名 -> QA列表的映射
            
        Returns:
            (合并后的QA列表, 统计信息)
        """
        all_qa = []
        stats = {
            "total_before": 0,
            "by_repo": {},
            "duplicates_removed": 0
        }
        
        # 收集所有数据
        for repo_name, qa_list in repo_qa_map.items():
            stats["by_repo"][repo_name] = len(qa_list)
            stats["total_before"] += len(qa_list)
            
            # 为每个QA添加源仓库信息
            for qa in qa_list:
                qa.metadata["source_repo"] = repo_name
                all_qa.append(qa)
        
        # 去重
        if self.deduplicate:
            original_count = len(all_qa)
            all_qa = self._deduplicate_qa(all_qa)
            stats["duplicates_removed"] = original_count - len(all_qa)
        
        # 打乱
        if self.shuffle:
            random.shuffle(all_qa)
        
        stats["total_after"] = len(all_qa)
        
        return all_qa, stats
    
    def merge_design_data(
        self,
        repo_design_map: Dict[str, List[DesignProposal]]
    ) -> Tuple[List[DesignProposal], Dict[str, Any]]:
        """
        合并设计方案数据
        
        Args:
            repo_design_map: 仓库名 -> 设计方案列表的映射
            
        Returns:
            (合并后的设计方案列表, 统计信息)
        """
        all_designs = []
        stats = {
            "total_before": 0,
            "by_repo": {},
            "duplicates_removed": 0
        }
        
        # 收集所有数据
        for repo_name, design_list in repo_design_map.items():
            stats["by_repo"][repo_name] = len(design_list)
            stats["total_before"] += len(design_list)
            
            # 为每个设计方案添加源仓库信息
            for design in design_list:
                design.metadata["source_repo"] = repo_name
                all_designs.append(design)
        
        # 去重
        if self.deduplicate:
            original_count = len(all_designs)
            all_designs = self._deduplicate_designs(all_designs)
            stats["duplicates_removed"] = original_count - len(all_designs)
        
        # 打乱
        if self.shuffle:
            random.shuffle(all_designs)
        
        stats["total_after"] = len(all_designs)
        
        return all_designs, stats
    
    def _deduplicate_qa(self, qa_list: List[QAPair]) -> List[QAPair]:
        """基于问题和答案内容去重"""
        seen = set()
        unique_qa = []
        
        for qa in qa_list:
            # 使用问题和答案的组合作为唯一标识
            key = f"{qa.question[:100]}||{qa.answer[:100]}"
            if key not in seen:
                seen.add(key)
                unique_qa.append(qa)
        
        return unique_qa
    
    def _deduplicate_designs(
        self,
        design_list: List[DesignProposal]
    ) -> List[DesignProposal]:
        """基于需求描述和源仓库去重
        
        注意：同一个需求在不同仓库中的设计方案应该被保留，
        因为不同代码库的架构和实现方式不同，设计方案也会不同。
        """
        seen = set()
        unique_designs = []
        
        for design in design_list:
            # 使用需求描述 + 源仓库作为唯一标识
            source_repo = design.metadata.get("source_repo", "unknown")
            key = f"{design.requirement[:200]}||{source_repo}"
            if key not in seen:
                seen.add(key)
                unique_designs.append(design)
        
        return unique_designs


class BatchManager:
    """
    批量处理管理器
    协调多个仓库的数据生成和处理
    """
    
    def __init__(
        self,
        max_qa_per_repo: Optional[int] = None,
        max_design_per_repo: Optional[int] = None,
        balance_strategy: str = "proportional",
        shuffle: bool = True,
        deduplicate: bool = True
    ):
        """
        初始化批量处理管理器
        
        Args:
            max_qa_per_repo: 每个仓库最大QA数量
            max_design_per_repo: 每个仓库最大设计方案数量
            balance_strategy: 平衡策略
            shuffle: 是否打乱数据
            deduplicate: 是否去重
        """
        self.balancer = BatchDataBalancer(
            max_qa_per_repo=max_qa_per_repo,
            max_design_per_repo=max_design_per_repo,
            balance_strategy=balance_strategy
        )
        self.merger = BatchDataMerger(
            shuffle=shuffle,
            deduplicate=deduplicate
        )
        self.repo_stats: List[RepoDataStats] = []
    
    def process_repositories(
        self,
        repo_qa_map: Dict[str, List[QAPair]],
        repo_design_map: Dict[str, List[DesignProposal]]
    ) -> Tuple[List[QAPair], List[DesignProposal], Dict[str, Any]]:
        """
        处理多个仓库的数据
        
        Args:
            repo_qa_map: 仓库名 -> QA列表的映射
            repo_design_map: 仓库名 -> 设计方案列表的映射
            
        Returns:
            (合并的QA列表, 合并的设计方案列表, 统计信息)
        """
        logger.info(f"开始处理 {len(repo_qa_map)} 个仓库的数据")
        
        # 1. 平衡数据
        logger.info("步骤 1/3: 平衡数据")
        balanced_qa = self.balancer.balance_qa_data(repo_qa_map)
        balanced_design = self.balancer.balance_design_data(repo_design_map)
        
        # 2. 合并数据
        logger.info("步骤 2/3: 合并数据")
        merged_qa, qa_stats = self.merger.merge_qa_data(balanced_qa)
        merged_design, design_stats = self.merger.merge_design_data(balanced_design)
        
        # 3. 生成统计信息
        logger.info("步骤 3/3: 生成统计")
        stats = self._generate_statistics(
            repo_qa_map,
            repo_design_map,
            balanced_qa,
            balanced_design,
            merged_qa,
            merged_design,
            qa_stats,
            design_stats
        )
        
        logger.info(f"处理完成: QA={len(merged_qa)}, Design={len(merged_design)}")
        
        return merged_qa, merged_design, stats
    
    def _generate_statistics(
        self,
        original_qa_map: Dict[str, List[QAPair]],
        original_design_map: Dict[str, List[DesignProposal]],
        balanced_qa_map: Dict[str, List[QAPair]],
        balanced_design_map: Dict[str, List[DesignProposal]],
        merged_qa: List[QAPair],
        merged_design: List[DesignProposal],
        qa_stats: Dict[str, Any],
        design_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成详细的统计信息"""
        
        # 按仓库统计
        repo_breakdown = {}
        all_repos = set(original_qa_map.keys()) | set(original_design_map.keys())
        
        for repo_name in all_repos:
            repo_breakdown[repo_name] = {
                "qa": {
                    "original": len(original_qa_map.get(repo_name, [])),
                    "balanced": len(balanced_qa_map.get(repo_name, [])),
                },
                "design": {
                    "original": len(original_design_map.get(repo_name, [])),
                    "balanced": len(balanced_design_map.get(repo_name, [])),
                }
            }
        
        # 语言分布统计
        language_dist = defaultdict(int)
        for qa in merged_qa:
            lang = qa.metadata.get("language", "unknown")
            language_dist[lang] += 1
        
        # 问题类型分布
        question_type_dist = defaultdict(int)
        for qa in merged_qa:
            question_type_dist[qa.question_type] += 1
        
        # 数据平衡度分析
        qa_counts = [len(items) for items in balanced_qa_map.values()]
        design_counts = [len(items) for items in balanced_design_map.values()]
        
        balance_metrics = {
            "qa_std_dev": self._calculate_std_dev(qa_counts) if qa_counts else 0,
            "design_std_dev": self._calculate_std_dev(design_counts) if design_counts else 0,
            "qa_balance_ratio": min(qa_counts) / max(qa_counts) if qa_counts and max(qa_counts) > 0 else 0,
            "design_balance_ratio": min(design_counts) / max(design_counts) if design_counts and max(design_counts) > 0 else 0,
        }
        
        return {
            "summary": {
                "total_repos": len(all_repos),
                "total_qa_original": sum(len(items) for items in original_qa_map.values()),
                "total_qa_final": len(merged_qa),
                "total_design_original": sum(len(items) for items in original_design_map.values()),
                "total_design_final": len(merged_design),
                "qa_removed": qa_stats["total_before"] - qa_stats["total_after"],
                "design_removed": design_stats["total_before"] - design_stats["total_after"],
            },
            "by_repo": repo_breakdown,
            "distributions": {
                "languages": dict(language_dist),
                "question_types": dict(question_type_dist),
            },
            "balance_metrics": balance_metrics,
            "merge_stats": {
                "qa": qa_stats,
                "design": design_stats
            }
        }
    
    def _calculate_std_dev(self, values: List[int]) -> float:
        """计算标准差"""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def save_batch_report(
        self,
        stats: Dict[str, Any],
        output_path: Path
    ):
        """
        保存批处理报告
        
        Args:
            stats: 统计信息
            output_path: 输出路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 添加时间戳
        stats["generated_at"] = datetime.now().isoformat()
        
        save_json(stats, output_path)
        logger.info(f"批处理报告已保存: {output_path}")
        
        # 同时生成 Markdown 报告
        md_path = output_path.with_suffix('.md')
        self._generate_markdown_report(stats, md_path)
    
    def _generate_markdown_report(
        self,
        stats: Dict[str, Any],
        output_path: Path
    ):
        """生成 Markdown 格式的报告"""
        summary = stats["summary"]
        
        content = f"""# 批量数据生成报告

## 概览

- **处理仓库数**: {summary['total_repos']}
- **生成时间**: {stats.get('generated_at', 'N/A')}

## 数据统计

### 问答对 (QA)

- 原始数据: {summary['total_qa_original']} 条
- 最终数据: {summary['total_qa_final']} 条
- 移除数据: {summary['qa_removed']} 条

### 设计方案 (Design)

- 原始数据: {summary['total_design_original']} 条
- 最终数据: {summary['total_design_final']} 条
- 移除数据: {summary['design_removed']} 条

## 各仓库贡献

| 仓库名称 | QA原始 | QA平衡后 | Design原始 | Design平衡后 |
|---------|--------|---------|-----------|-------------|
"""
        
        for repo_name, repo_stats in stats["by_repo"].items():
            qa = repo_stats["qa"]
            design = repo_stats["design"]
            content += f"| {repo_name} | {qa['original']} | {qa['balanced']} | {design['original']} | {design['balanced']} |\n"
        
        # 添加语言分布
        content += "\n## 编程语言分布\n\n"
        for lang, count in sorted(
            stats["distributions"]["languages"].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            content += f"- **{lang}**: {count} 条\n"
        
        # 添加问题类型分布
        content += "\n## 问题类型分布\n\n"
        for qtype, count in sorted(
            stats["distributions"]["question_types"].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            content += f"- **{qtype}**: {count} 条\n"
        
        # 平衡度指标
        balance = stats["balance_metrics"]
        content += f"""
## 数据平衡度分析

- **QA 平衡比**: {balance['qa_balance_ratio']:.2%}
- **QA 标准差**: {balance['qa_std_dev']:.2f}
- **Design 平衡比**: {balance['design_balance_ratio']:.2%}
- **Design 标准差**: {balance['design_std_dev']:.2f}

> 平衡比越接近100%表示各仓库贡献越均衡
"""
        
        output_path.write_text(content, encoding='utf-8')
        logger.info(f"Markdown 报告已保存: {output_path}")

