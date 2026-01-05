#!/usr/bin/env python3
"""
列出 DashScope 中可用的微调模型
"""

import os
import sys

try:
    import dashscope
except ImportError:
    print("❌ 错误: 未安装 dashscope SDK")
    print("请运行: pip3 install dashscope --user")
    sys.exit(1)

def list_finetuned_models():
    """列出所有微调模型"""
    
    # 设置 API Key
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        print("❌ 错误: 未设置 DASHSCOPE_API_KEY")
        print("请运行: export DASHSCOPE_API_KEY='your-api-key'")
        sys.exit(1)
    
    dashscope.api_key = api_key
    
    print("="*60)
    print("DashScope 微调模型列表")
    print("="*60)
    print()
    
    try:
        # 尝试获取微调任务列表
        from dashscope.finetuning import FineTuning
        
        # 列出最近的微调任务
        response = FineTuning.list()
        
        if response.status_code == 200:
            jobs = response.output.get('job_list', [])
            
            if not jobs:
                print("📋 暂无微调任务")
                return
            
            print(f"找到 {len(jobs)} 个微调任务:\n")
            
            for i, job in enumerate(jobs, 1):
                job_id = job.get('job_id', 'N/A')
                status = job.get('status', 'N/A')
                model = job.get('model', 'N/A')
                created_time = job.get('created_time', 'N/A')
                
                print(f"{i}. 任务 ID: {job_id}")
                print(f"   状态: {status}")
                print(f"   基础模型: {model}")
                print(f"   创建时间: {created_time}")
                
                # 如果任务成功，显示微调后的模型 ID
                if status == 'SUCCEEDED':
                    fine_tuned_model = job.get('fine_tuned_model', 'N/A')
                    print(f"   ✅ 微调模型: {fine_tuned_model}")
                    print(f"\n   使用此模型 ID 进行评估:")
                    print(f"   python scripts/evaluate_finetuned_model.py \\")
                    print(f"       --model {fine_tuned_model} \\")
                    print(f"       --test-file output/dashscope/test.jsonl")
                elif status == 'RUNNING':
                    print(f"   ⏳ 训练中...")
                elif status == 'FAILED':
                    print(f"   ❌ 训练失败")
                    error_msg = job.get('error_message', '')
                    if error_msg:
                        print(f"   错误: {error_msg}")
                
                print()
        else:
            print(f"❌ 获取失败: {response.message}")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        print("提示: 请确保:")
        print("1. API Key 正确")
        print("2. 网络连接正常")
        print("3. 已安装最新版 dashscope SDK")
        print()
        print("手动查看模型:")
        print("访问 https://dashscope.console.aliyun.com/finetuning")

if __name__ == "__main__":
    list_finetuned_models()

