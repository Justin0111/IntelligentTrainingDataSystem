#!/usr/bin/env python3
"""
评估结果分析工具 - 计算直观指标并对比模型效果
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import re


class EvaluationAnalyzer:
    """评估结果分析器"""
    
    def __init__(self, results_file: str):
        """加载评估结果"""
        with open(results_file, 'r', encoding='utf-8') as f:
            self.results = json.load(f)
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """计算评估指标"""
        predictions = self.results.get('predictions', [])
        
        metrics = {
            'basic': self._calculate_basic_metrics(),
            'content': self._calculate_content_metrics(predictions),
            'structure': self._calculate_structure_metrics(predictions),
            'quality': self._calculate_quality_metrics(predictions)
        }
        
        return metrics
    
    def _calculate_basic_metrics(self) -> Dict[str, Any]:
        """基础指标"""
        return {
            'total_samples': self.results['total_samples'],
            'successful': self.results['successful'],
            'failed': self.results['failed'],
            'success_rate': self.results['successful'] / self.results['total_samples'] * 100,
            'total_input_tokens': self.results['metrics']['total_input_tokens'],
            'total_output_tokens': self.results['metrics']['total_output_tokens'],
            'avg_input_tokens': self.results['metrics']['total_input_tokens'] / self.results['successful'],
            'avg_output_tokens': self.results['metrics']['total_output_tokens'] / self.results['successful'],
            'avg_response_length': self.results['metrics']['avg_response_length']
        }
    
    def _calculate_content_metrics(self, predictions: List[Dict]) -> Dict[str, Any]:
        """内容质量指标"""
        reasoning_count = 0
        conclusion_count = 0
        code_ref_count = 0
        
        for pred in predictions:
            predicted = pred.get('predicted', '')
            
            # 检查是否包含推理过程
            if '推理过程' in predicted or '步骤' in predicted:
                reasoning_count += 1
            
            # 检查是否有结论
            if '结论' in predicted or '总结' in predicted or '综上' in predicted:
                conclusion_count += 1
            
            # 检查是否引用代码
            if '代码' in predicted or '函数' in predicted or '方法' in predicted:
                code_ref_count += 1
        
        total = len(predictions)
        return {
            'reasoning_coverage': reasoning_count / total * 100,
            'conclusion_coverage': conclusion_count / total * 100,
            'code_reference_coverage': code_ref_count / total * 100,
            'reasoning_count': reasoning_count,
            'conclusion_count': conclusion_count,
            'code_ref_count': code_ref_count
        }
    
    def _calculate_structure_metrics(self, predictions: List[Dict]) -> Dict[str, Any]:
        """结构化指标"""
        step_pattern = re.compile(r'步骤\d+')
        
        total_steps = 0
        multi_step_count = 0
        
        for pred in predictions:
            predicted = pred.get('predicted', '')
            steps = step_pattern.findall(predicted)
            
            if len(steps) > 0:
                total_steps += len(steps)
                if len(steps) >= 2:
                    multi_step_count += 1
        
        total = len(predictions)
        return {
            'avg_reasoning_steps': total_steps / total,
            'multi_step_ratio': multi_step_count / total * 100,
            'total_steps': total_steps,
            'multi_step_count': multi_step_count
        }
    
    def _calculate_quality_metrics(self, predictions: List[Dict]) -> Dict[str, Any]:
        """质量指标"""
        # 计算响应长度分布
        lengths = [len(p.get('predicted', '')) for p in predictions]
        lengths.sort()
        
        # 计算完整性得分（基于关键词）
        completeness_scores = []
        for pred in predictions:
            predicted = pred.get('predicted', '')
            score = 0
            
            # 检查关键元素
            if '推理过程' in predicted or '步骤' in predicted:
                score += 0.4
            if len(predicted) > 100:  # 有实质内容
                score += 0.3
            if '函数' in predicted or '代码' in predicted or '方法' in predicted:
                score += 0.3
            
            completeness_scores.append(score)
        
        return {
            'min_length': min(lengths),
            'max_length': max(lengths),
            'median_length': lengths[len(lengths) // 2],
            'avg_completeness_score': sum(completeness_scores) / len(completeness_scores) * 100
        }
    
    def print_report(self, metrics: Dict[str, Any]):
        """打印分析报告"""
        print("="*70)
        print(" "*20 + "微调模型评估报告")
        print("="*70)
        print()
        
        # 基础指标
        basic = metrics['basic']
        print("📊 基础指标")
        print("-"*70)
        print(f"  测试样本数:     {basic['total_samples']}")
        print(f"  成功:           {basic['successful']}")
        print(f"  失败:           {basic['failed']}")
        print(f"  成功率:         {basic['success_rate']:.1f}%")
        print()
        
        # Token 使用
        print("💰 Token 使用统计")
        print("-"*70)
        print(f"  总输入 tokens:  {basic['total_input_tokens']:,}")
        print(f"  总输出 tokens:  {basic['total_output_tokens']:,}")
        print(f"  平均输入:       {basic['avg_input_tokens']:.1f} tokens/条")
        print(f"  平均输出:       {basic['avg_output_tokens']:.1f} tokens/条")
        print()
        
        # 内容质量
        content = metrics['content']
        print("📝 内容质量指标")
        print("-"*70)
        print(f"  包含推理过程:   {content['reasoning_count']}/{basic['total_samples']} ({content['reasoning_coverage']:.1f}%)")
        print(f"  包含结论:       {content['conclusion_count']}/{basic['total_samples']} ({content['conclusion_coverage']:.1f}%)")
        print(f"  引用代码:       {content['code_ref_count']}/{basic['total_samples']} ({content['code_reference_coverage']:.1f}%)")
        print()
        
        # 结构化程度
        structure = metrics['structure']
        print("🔍 结构化程度")
        print("-"*70)
        print(f"  平均推理步骤:   {structure['avg_reasoning_steps']:.1f} 步/条")
        print(f"  多步推理比例:   {structure['multi_step_count']}/{basic['total_samples']} ({structure['multi_step_ratio']:.1f}%)")
        print()
        
        # 质量评估
        quality = metrics['quality']
        print("⭐ 整体质量评估")
        print("-"*70)
        print(f"  平均响应长度:   {basic['avg_response_length']:.0f} 字符")
        print(f"  响应长度中位数: {quality['median_length']} 字符")
        print(f"  最短响应:       {quality['min_length']} 字符")
        print(f"  最长响应:       {quality['max_length']} 字符")
        print(f"  完整性得分:     {quality['avg_completeness_score']:.1f}%")
        print()
        
        # 综合评分
        self._print_overall_score(metrics)
    
    def _print_overall_score(self, metrics: Dict[str, Any]):
        """打印综合评分"""
        print("="*70)
        print(" "*25 + "综合评分")
        print("="*70)
        print()
        
        # 计算各维度得分
        basic = metrics['basic']
        content = metrics['content']
        structure = metrics['structure']
        quality = metrics['quality']
        
        success_score = min(basic['success_rate'], 100)
        reasoning_score = content['reasoning_coverage']
        structure_score = min(structure['avg_reasoning_steps'] * 30, 100)
        completeness_score = quality['avg_completeness_score']
        
        # 加权综合得分
        overall_score = (
            success_score * 0.2 +
            reasoning_score * 0.3 +
            structure_score * 0.2 +
            completeness_score * 0.3
        )
        
        print(f"  成功率得分:     {success_score:.1f}/100  (权重: 20%)")
        print(f"  推理完整性:     {reasoning_score:.1f}/100  (权重: 30%)")
        print(f"  结构化程度:     {structure_score:.1f}/100  (权重: 20%)")
        print(f"  内容完整性:     {completeness_score:.1f}/100  (权重: 30%)")
        print()
        print(f"  {'='*70}")
        print(f"  综合得分:       {overall_score:.1f}/100")
        print(f"  {'='*70}")
        print()
        
        # 评级
        if overall_score >= 90:
            grade = "A+ (优秀)"
        elif overall_score >= 80:
            grade = "A (良好)"
        elif overall_score >= 70:
            grade = "B (中等)"
        elif overall_score >= 60:
            grade = "C (及格)"
        else:
            grade = "D (需改进)"
        
        print(f"  模型评级:       {grade}")
        print()
    
    def compare_samples(self, num_samples: int = 5):
        """对比预期和实际输出示例"""
        print("="*70)
        print(" "*20 + "预测示例对比")
        print("="*70)
        print()
        
        predictions = self.results.get('predictions', [])[:num_samples]
        
        for i, pred in enumerate(predictions, 1):
            print(f"{'─'*70}")
            print(f"示例 {i}: {pred['prompt'][:60]}...")
            print(f"{'─'*70}")
            print()
            
            print("📌 期望输出:")
            print(f"{pred['expected'][:300]}...")
            print()
            
            print("🤖 模型输出:")
            print(f"{pred['predicted'][:300]}...")
            print()
            
            print(f"📊 Token 使用: 输入 {pred['usage']['input_tokens']}, "
                  f"输出 {pred['usage']['output_tokens']}")
            print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='分析微调模型评估结果',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'results_file',
        type=str,
        help='评估结果文件路径（JSON 格式）'
    )
    
    parser.add_argument(
        '--samples',
        type=int,
        default=5,
        help='显示的对比示例数量（默认: 5）'
    )
    
    parser.add_argument(
        '--export',
        type=str,
        help='导出分析报告到文件'
    )
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    results_path = Path(args.results_file)
    if not results_path.exists():
        print(f"❌ 错误: 文件不存在: {args.results_file}")
        sys.exit(1)
    
    # 分析结果
    analyzer = EvaluationAnalyzer(args.results_file)
    metrics = analyzer.calculate_metrics()
    
    # 打印报告
    analyzer.print_report(metrics)
    analyzer.compare_samples(args.samples)
    
    # 导出报告
    if args.export:
        export_path = Path(args.export)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 分析报告已导出: {export_path}")


if __name__ == "__main__":
    main()

