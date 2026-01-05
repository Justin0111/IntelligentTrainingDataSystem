#!/usr/bin/env python3
"""
对比微调模型和基础模型的效果
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List

try:
    from dashscope import Generation
except ImportError:
    print("❌ 错误: 未安装 dashscope SDK")
    sys.exit(1)


class ModelComparator:
    """模型对比器"""
    
    def __init__(self, base_model: str, finetuned_model: str, api_key: str = None):
        self.base_model = base_model
        self.finetuned_model = finetuned_model
        
        # 设置 API Key
        if api_key:
            self.api_key = api_key
        elif 'DASHSCOPE_API_KEY' in os.environ:
            self.api_key = os.environ['DASHSCOPE_API_KEY']
        else:
            raise ValueError("未设置 API Key")
    
    def generate_response(self, model: str, prompt: str) -> Dict:
        """生成回答"""
        try:
            response = Generation.call(
                model=model,
                prompt=prompt,
                max_tokens=500,
                api_key=self.api_key
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "text": response.output.text,
                    "usage": response.usage
                }
            else:
                return {
                    "success": False,
                    "error": response.message
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def compare_on_samples(
        self,
        test_file: str,
        num_samples: int = 10,
        delay: float = 0.5
    ) -> Dict:
        """对比测试样本"""
        # 加载测试数据
        with open(test_file, 'r', encoding='utf-8') as f:
            test_data = []
            for line in f:
                line = line.strip()
                if line:
                    test_data.append(json.loads(line))
        
        test_data = test_data[:num_samples]
        
        results = {
            "base_model": self.base_model,
            "finetuned_model": self.finetuned_model,
            "total_samples": len(test_data),
            "comparisons": []
        }
        
        print(f"\n📊 开始对比测试 (共 {len(test_data)} 条)...")
        print()
        
        for i, item in enumerate(test_data, 1):
            # 提取 prompt
            if "messages" in item:
                messages = item["messages"]
                user_messages = [m for m in messages if m.get("role") == "user"]
                if user_messages:
                    prompt = user_messages[0].get("content", "")
                else:
                    continue
            else:
                continue
            
            print(f"  [{i}/{len(test_data)}] 测试中...", end="\r")
            
            # 基础模型回答
            base_response = self.generate_response(self.base_model, prompt)
            time.sleep(delay)
            
            # 微调模型回答
            ft_response = self.generate_response(self.finetuned_model, prompt)
            time.sleep(delay)
            
            comparison = {
                "index": i,
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "base_response": base_response.get("text", "") if base_response["success"] else f"错误: {base_response.get('error', '')}",
                "finetuned_response": ft_response.get("text", "") if ft_response["success"] else f"错误: {ft_response.get('error', '')}",
                "base_length": len(base_response.get("text", "")) if base_response["success"] else 0,
                "ft_length": len(ft_response.get("text", "")) if ft_response["success"] else 0
            }
            
            results["comparisons"].append(comparison)
        
        print()
        return results
    
    def print_comparison_report(self, results: Dict):
        """打印对比报告"""
        print("\n" + "="*70)
        print(" "*20 + "模型对比报告")
        print("="*70)
        print()
        
        print(f"📌 基础模型: {results['base_model']}")
        print(f"🎯 微调模型: {results['finetuned_model']}")
        print(f"📊 测试样本: {results['total_samples']} 条")
        print()
        
        # 统计对比
        comparisons = results['comparisons']
        
        base_lengths = [c['base_length'] for c in comparisons if c['base_length'] > 0]
        ft_lengths = [c['ft_length'] for c in comparisons if c['ft_length'] > 0]
        
        # 检查推理过程
        base_reasoning = sum(1 for c in comparisons if '推理' in c['base_response'] or '步骤' in c['base_response'])
        ft_reasoning = sum(1 for c in comparisons if '推理' in c['finetuned_response'] or '步骤' in c['finetuned_response'])
        
        # 检查结构化
        base_structured = sum(1 for c in comparisons if '步骤1' in c['base_response'])
        ft_structured = sum(1 for c in comparisons if '步骤1' in c['finetuned_response'])
        
        print("="*70)
        print(" "*25 + "对比结果")
        print("="*70)
        print()
        
        print(f"{'指标':<20} {'基础模型':<20} {'微调模型':<20} {'提升':<10}")
        print("-"*70)
        
        # 平均长度
        avg_base = sum(base_lengths) / len(base_lengths) if base_lengths else 0
        avg_ft = sum(ft_lengths) / len(ft_lengths) if ft_lengths else 0
        improvement = ((avg_ft - avg_base) / avg_base * 100) if avg_base > 0 else 0
        print(f"{'平均回答长度':<20} {avg_base:<20.0f} {avg_ft:<20.0f} {improvement:>+.1f}%")
        
        # 推理过程覆盖率
        base_rate = base_reasoning / len(comparisons) * 100
        ft_rate = ft_reasoning / len(comparisons) * 100
        improvement = ft_rate - base_rate
        print(f"{'推理过程覆盖':<20} {base_rate:<20.1f}% {ft_rate:<20.1f}% {improvement:>+.1f}%")
        
        # 结构化程度
        base_struct_rate = base_structured / len(comparisons) * 100
        ft_struct_rate = ft_structured / len(comparisons) * 100
        improvement = ft_struct_rate - base_struct_rate
        print(f"{'结构化回答':<20} {base_struct_rate:<20.1f}% {ft_struct_rate:<20.1f}% {improvement:>+.1f}%")
        
        print()
        
        # 示例对比
        print("="*70)
        print(" "*25 + "对比示例")
        print("="*70)
        
        for i, comp in enumerate(results['comparisons'][:3], 1):
            print()
            print(f"{'─'*70}")
            print(f"示例 {i}: {comp['prompt']}")
            print(f"{'─'*70}")
            print()
            
            print("📌 基础模型回答:")
            print(comp['base_response'][:200] + "..." if len(comp['base_response']) > 200 else comp['base_response'])
            print()
            
            print("🎯 微调模型回答:")
            print(comp['finetuned_response'][:200] + "..." if len(comp['finetuned_response']) > 200 else comp['finetuned_response'])
            print()
        
        print("="*70)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='对比微调模型和基础模型的效果',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--base-model',
        type=str,
        default='qwen-turbo',
        help='基础模型 ID（默认: qwen-turbo）'
    )
    
    parser.add_argument(
        '--finetuned-model',
        type=str,
        required=True,
        help='微调模型 ID'
    )
    
    parser.add_argument(
        '--test-file',
        type=str,
        required=True,
        help='测试数据文件'
    )
    
    parser.add_argument(
        '--samples',
        type=int,
        default=10,
        help='测试样本数量（默认: 10）'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='保存对比结果到文件'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='DashScope API Key'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print(" "*20 + "模型对比工具")
    print("="*70)
    
    # 创建对比器
    try:
        comparator = ModelComparator(
            args.base_model,
            args.finetuned_model,
            args.api_key
        )
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 执行对比
    try:
        results = comparator.compare_on_samples(
            args.test_file,
            args.samples
        )
        
        # 打印报告
        comparator.print_comparison_report(results)
        
        # 保存结果
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 对比结果已保存: {output_path}")
    
    except Exception as e:
        print(f"\n❌ 对比失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

