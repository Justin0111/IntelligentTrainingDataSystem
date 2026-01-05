#!/usr/bin/env python3
"""
测试微调模型是否可用
"""

import os
import sys

try:
    from dashscope import Generation
except ImportError:
    print("❌ 错误: 未安装 dashscope SDK")
    sys.exit(1)

def test_model(model_id: str, test_prompt: str = "你好"):
    """
    测试模型是否可用
    
    Args:
        model_id: 模型 ID
        test_prompt: 测试提示
    """
    # 设置 API Key
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        print("❌ 错误: 未设置 DASHSCOPE_API_KEY")
        print("请运行: export DASHSCOPE_API_KEY='your-api-key'")
        sys.exit(1)
    
    print("="*60)
    print("微调模型可用性测试")
    print("="*60)
    print()
    print(f"模型 ID: {model_id}")
    print(f"测试提示: {test_prompt}")
    print()
    print("正在调用模型...")
    print()
    
    try:
        response = Generation.call(
            model=model_id,
            prompt=test_prompt,
            max_tokens=100,
            api_key=api_key
        )
        
        if response.status_code == 200:
            print("✅ 模型可用！")
            print()
            print("="*60)
            print("模型回答:")
            print("="*60)
            print(response.output.text)
            print()
            print("="*60)
            print("Token 使用:")
            print(f"  输入: {response.usage.input_tokens} tokens")
            print(f"  输出: {response.usage.output_tokens} tokens")
            print("="*60)
            print()
            print("✅ 测试成功！模型已经可以使用了。")
            print()
            print("下一步: 运行完整评估")
            print(f"python scripts/evaluate_finetuned_model.py \\")
            print(f"    --model {model_id} \\")
            print(f"    --test-file output/dashscope/test.jsonl")
            return True
            
        else:
            print(f"❌ 调用失败")
            print(f"状态码: {response.status_code}")
            print(f"错误信息: {response.message}")
            print()
            
            # 提供详细的错误解释
            if "not exist" in response.message.lower():
                print("💡 可能原因:")
                print("1. 模型还在部署中（训练完成后需要 3-5 分钟）")
                print("2. 模型 ID 不正确")
                print()
                print("解决方法:")
                print("1. 等待 5 分钟后重试")
                print("2. 访问控制台确认模型 ID:")
                print("   https://dashscope.console.aliyun.com/finetuning")
            
            return False
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='测试微调模型是否可用')
    parser.add_argument('--model', type=str, required=True, help='模型 ID')
    parser.add_argument('--prompt', type=str, default='请解释什么是函数？', 
                       help='测试提示（默认: 请解释什么是函数？）')
    
    args = parser.parse_args()
    
    success = test_model(args.model, args.prompt)
    sys.exit(0 if success else 1)

