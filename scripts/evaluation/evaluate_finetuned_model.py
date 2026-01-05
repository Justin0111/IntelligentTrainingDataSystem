#!/usr/bin/env python3
"""
微调模型评估脚本 - 评估微调后的模型在测试集上的表现
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

try:
    import dashscope
    from dashscope import Generation
except ImportError:
    print("❌ 错误: 未安装 dashscope SDK")
    print("请运行: pip3 install dashscope --user")
    print("或在虚拟环境中: pip install dashscope")
    sys.exit(1)


class ModelEvaluator:
    """模型评估器"""
    
    def __init__(self, model_id: str, api_key: str = None):
        """
        初始化评估器
        
        Args:
            model_id: 模型 ID
            api_key: API Key
        """
        self.model_id = model_id
        
        # 设置 API Key
        if api_key:
            dashscope.api_key = api_key
        elif 'DASHSCOPE_API_KEY' in os.environ:
            dashscope.api_key = os.environ['DASHSCOPE_API_KEY']
        else:
            raise ValueError("未设置 API Key")
    
    def load_test_data(self, test_file: str) -> List[Dict[str, Any]]:
        """加载测试数据"""
        test_path = Path(test_file)
        
        if not test_path.exists():
            raise FileNotFoundError(f"测试文件不存在: {test_path}")
        
        data = []
        with open(test_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        
        return data
    
    def generate_response(self, prompt: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        生成回答
        
        Args:
            prompt: 输入提示
            max_tokens: 最大生成token数
            
        Returns:
            生成结果字典
        """
        try:
            response = Generation.call(
                model=self.model_id,
                prompt=prompt,
                max_tokens=max_tokens
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
    
    def evaluate(
        self,
        test_data: List[Dict[str, Any]],
        max_samples: int = None,
        delay: float = 0.5
    ) -> Dict[str, Any]:
        """
        评估模型
        
        Args:
            test_data: 测试数据
            max_samples: 最大测试样本数
            delay: 请求之间的延迟（秒）
            
        Returns:
            评估结果
        """
        if max_samples:
            test_data = test_data[:max_samples]
        
        results = {
            "model_id": self.model_id,
            "total_samples": len(test_data),
            "successful": 0,
            "failed": 0,
            "predictions": [],
            "metrics": {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "avg_response_length": 0
            }
        }
        
        print(f"📊 开始评估 (共 {len(test_data)} 条测试数据)...")
        
        total_response_length = 0
        
        for i, item in enumerate(test_data, 1):
            # 构建 prompt
            if "prompt" in item:
                prompt = item["prompt"]
            elif "instruction" in item:
                prompt = item["instruction"]
                if item.get("input"):
                    prompt = f"{prompt}\n\n{item['input']}"
            elif "messages" in item:
                # 支持 messages 格式（ChatML）
                messages = item["messages"]
                # 提取 user 消息作为 prompt
                user_messages = [m for m in messages if m.get("role") == "user"]
                if user_messages:
                    prompt = user_messages[0].get("content", "")
                else:
                    print(f"⚠️  第 {i} 条: messages 中无 user 角色")
                    continue
            else:
                print(f"⚠️  第 {i} 条: 无法提取 prompt")
                continue
            
            # 生成回答
            print(f"  [{i}/{len(test_data)}] 生成中...", end="\r")
            
            result = self.generate_response(prompt)
            
            if result["success"]:
                results["successful"] += 1
                
                # 提取参考答案
                expected = None
                if "response" in item:
                    expected = item["response"]
                elif "output" in item:
                    expected = item["output"]
                elif "messages" in item:
                    # 从 messages 中提取 assistant 的回答
                    assistant_messages = [m for m in item["messages"] if m.get("role") == "assistant"]
                    if assistant_messages:
                        expected = assistant_messages[0].get("content", "")
                
                # 记录预测结果
                prediction = {
                    "index": i,
                    "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                    "expected": expected,
                    "predicted": result["text"],
                    "usage": result["usage"]
                }
                
                results["predictions"].append(prediction)
                
                # 更新统计
                results["metrics"]["total_input_tokens"] += result["usage"]["input_tokens"]
                results["metrics"]["total_output_tokens"] += result["usage"]["output_tokens"]
                total_response_length += len(result["text"])
            else:
                results["failed"] += 1
                print(f"\n⚠️  第 {i} 条失败: {result['error']}")
            
            # 延迟以避免超过速率限制
            time.sleep(delay)
        
        print()  # 换行
        
        # 计算平均值
        if results["successful"] > 0:
            results["metrics"]["avg_response_length"] = total_response_length / results["successful"]
        
        return results
    
    def save_results(self, results: Dict[str, Any], output_file: str):
        """保存评估结果"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"💾 结果已保存: {output_path}")
    
    def print_summary(self, results: Dict[str, Any]):
        """打印评估摘要"""
        print(f"\n{'='*60}")
        print("📊 评估结果摘要")
        print(f"{'='*60}")
        
        print(f"\n模型: {results['model_id']}")
        print(f"测试样本数: {results['total_samples']}")
        print(f"成功: {results['successful']}")
        print(f"失败: {results['failed']}")
        
        if results['successful'] > 0:
            success_rate = results['successful'] / results['total_samples'] * 100
            print(f"成功率: {success_rate:.1f}%")
        
        print(f"\n📈 Token 使用统计:")
        print(f"  输入 tokens: {results['metrics']['total_input_tokens']}")
        print(f"  输出 tokens: {results['metrics']['total_output_tokens']}")
        print(f"  总计: {results['metrics']['total_input_tokens'] + results['metrics']['total_output_tokens']}")
        
        if results['successful'] > 0:
            avg_input = results['metrics']['total_input_tokens'] / results['successful']
            avg_output = results['metrics']['total_output_tokens'] / results['successful']
            print(f"\n  平均输入: {avg_input:.1f} tokens/条")
            print(f"  平均输出: {avg_output:.1f} tokens/条")
        
        print(f"\n📝 回答长度:")
        print(f"  平均: {results['metrics']['avg_response_length']:.0f} 字符")
        
        # 显示示例
        if results['predictions']:
            print(f"\n{'='*60}")
            print("📝 预测示例 (前 3 条)")
            print(f"{'='*60}")
            
            for pred in results['predictions'][:3]:
                print(f"\n--- 示例 {pred['index']} ---")
                print(f"Prompt: {pred['prompt']}")
                print(f"\n预期回答: {pred['expected'][:200]}...")
                print(f"\n模型回答: {pred['predicted'][:200]}...")
                print()


def main():
    parser = argparse.ArgumentParser(
        description='评估微调后的模型',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 评估模型
  python evaluate_finetuned_model.py \
      --model ft-qwen-turbo-xxxx \
      --test-file output/dashscope/test.jsonl \
      --output output/evaluation/results.json
  
  # 限制测试样本数量（快速测试）
  python evaluate_finetuned_model.py \
      --model ft-qwen-turbo-xxxx \
      --test-file test.jsonl \
      --max-samples 20
        """
    )
    
    parser.add_argument(
        '--model',
        type=str,
        required=True,
        help='微调后的模型 ID'
    )
    
    parser.add_argument(
        '--test-file',
        type=str,
        required=True,
        help='测试数据文件路径'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='结果输出文件路径（JSON 格式）'
    )
    
    parser.add_argument(
        '--max-samples',
        type=int,
        help='最大测试样本数（用于快速测试）'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='请求之间的延迟（秒，默认: 0.5）'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='DashScope API Key'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("微调模型评估工具")
    print("="*60)
    
    # 创建评估器
    try:
        evaluator = ModelEvaluator(args.model, args.api_key)
        print(f"\n✅ 模型: {args.model}")
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 加载测试数据
    print(f"📖 加载测试数据: {args.test_file}")
    
    try:
        test_data = evaluator.load_test_data(args.test_file)
        print(f"✅ 成功加载 {len(test_data)} 条测试数据")
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        sys.exit(1)
    
    # 执行评估
    results = evaluator.evaluate(
        test_data,
        max_samples=args.max_samples,
        delay=args.delay
    )
    
    # 显示摘要
    evaluator.print_summary(results)
    
    # 保存结果
    if args.output:
        evaluator.save_results(results, args.output)
    else:
        # 默认输出路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = f"output/evaluation/results_{timestamp}.json"
        evaluator.save_results(results, default_output)


if __name__ == '__main__':
    main()

