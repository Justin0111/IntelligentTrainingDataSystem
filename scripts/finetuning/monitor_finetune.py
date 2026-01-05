#!/usr/bin/env python3
"""
DashScope 微调监控脚本 - 监控正在进行的微调任务
"""

import os
import sys
import time
import argparse
from pathlib import Path

try:
    import dashscope
    from dashscope import FineTunes
except ImportError:
    print("❌ 错误: 未安装 dashscope SDK")
    print("请运行: pip3 install dashscope --user")
    print("或在虚拟环境中: pip install dashscope")
    sys.exit(1)


def monitor_job(job_id: str, check_interval: int = 30, api_key: str = None):
    """
    监控微调任务
    
    Args:
        job_id: 任务 ID
        check_interval: 检查间隔（秒）
        api_key: API Key（可选）
    """
    # 设置 API Key
    if api_key:
        dashscope.api_key = api_key
    elif 'DASHSCOPE_API_KEY' in os.environ:
        dashscope.api_key = os.environ['DASHSCOPE_API_KEY']
    else:
        print("❌ 错误: 未设置 API Key")
        print("请设置环境变量 DASHSCOPE_API_KEY 或使用 --api-key 参数")
        sys.exit(1)
    
    print(f"📊 监控微调任务: {job_id}")
    print(f"  检查间隔: {check_interval} 秒")
    print("  提示: 按 Ctrl+C 可以退出监控（任务会继续运行）\n")
    
    last_status = None
    last_progress = None
    start_time = time.time()
    
    try:
        while True:
            try:
                response = FineTunes.get(job_id)
                
                if response.status_code != 200:
                    print(f"❌ 获取任务状态失败: {response.message}")
                    time.sleep(check_interval)
                    continue
                
                status = response.output.status
                elapsed = int(time.time() - start_time)
                
                # 如果状态改变，显示更新
                if status != last_status:
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[{timestamp}] ({elapsed}s) 状态: {status}")
                    last_status = status
                
                # 显示进度（如果有）
                if hasattr(response.output, 'progress'):
                    progress = response.output.progress
                    if progress != last_progress:
                        print(f"  进度: {progress}%")
                        last_progress = progress
                
                # 显示指标（如果有）
                if hasattr(response.output, 'metrics') and status == 'RUNNING':
                    metrics = response.output.metrics
                    if metrics:
                        print(f"  指标: ", end="")
                        metric_strs = [f"{k}={v:.4f}" for k, v in metrics.items()]
                        print(", ".join(metric_strs))
                
                # 检查是否完成
                if status == 'SUCCEEDED':
                    print(f"\n{'='*60}")
                    print("✅ 训练完成!")
                    print(f"{'='*60}")
                    
                    fine_tuned_model = response.output.fine_tuned_model
                    print(f"\n📦 微调后的模型:")
                    print(f"  模型 ID: {fine_tuned_model}")
                    
                    # 显示最终指标
                    if hasattr(response.output, 'metrics'):
                        print(f"\n📊 最终指标:")
                        metrics = response.output.metrics
                        for key, value in metrics.items():
                            print(f"  - {key}: {value}")
                    
                    # 显示使用示例
                    print(f"\n💡 使用示例:")
                    print(f"```python")
                    print(f"from dashscope import Generation")
                    print(f"")
                    print(f"response = Generation.call(")
                    print(f"    model='{fine_tuned_model}',")
                    print(f"    prompt='你的问题',")
                    print(f"    max_tokens=500")
                    print(f")")
                    print(f"print(response.output.text)")
                    print(f"```")
                    
                    # 保存模型信息
                    save_model_info(job_id, fine_tuned_model)
                    
                    break
                
                elif status == 'FAILED':
                    print(f"\n{'='*60}")
                    print("❌ 训练失败!")
                    print(f"{'='*60}")
                    
                    if hasattr(response.output, 'error'):
                        print(f"\n错误信息: {response.output.error}")
                    
                    if hasattr(response.output, 'error_message'):
                        print(f"详细信息: {response.output.error_message}")
                    
                    break
                
                elif status == 'CANCELLED':
                    print(f"\n⚠️  训练已取消")
                    break
                
                # 等待下次检查
                time.sleep(check_interval)
            
            except Exception as e:
                print(f"⚠️  检查时出错: {e}")
                time.sleep(check_interval)
    
    except KeyboardInterrupt:
        print(f"\n\n⚠️  监控已停止（任务仍在运行）")
        print(f"  任务 ID: {job_id}")
        print(f"  稍后可以继续监控:")
        print(f"  python scripts/monitor_finetune.py {job_id}")


def save_model_info(job_id: str, model_id: str):
    """保存模型信息"""
    output_dir = Path("output/models")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    info_file = output_dir / f"model_{model_id.replace('/', '_')}.txt"
    
    with open(info_file, 'w', encoding='utf-8') as f:
        f.write(f"任务 ID: {job_id}\n")
        f.write(f"模型 ID: {model_id}\n")
        f.write(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"\n💾 模型信息已保存: {info_file}")


def list_jobs(api_key: str = None):
    """列出所有微调任务"""
    # 设置 API Key
    if api_key:
        dashscope.api_key = api_key
    elif 'DASHSCOPE_API_KEY' in os.environ:
        dashscope.api_key = os.environ['DASHSCOPE_API_KEY']
    else:
        print("❌ 错误: 未设置 API Key")
        sys.exit(1)
    
    print("📋 获取微调任务列表...\n")
    
    try:
        response = FineTunes.list()
        
        if response.status_code != 200:
            print(f"❌ 获取任务列表失败: {response.message}")
            return
        
        jobs = response.output.data
        
        if not jobs:
            print("没有找到任何微调任务")
            return
        
        print(f"共找到 {len(jobs)} 个微调任务:\n")
        
        for i, job in enumerate(jobs, 1):
            print(f"{i}. {job.job_id}")
            print(f"   状态: {job.status}")
            print(f"   模型: {job.model}")
            
            if hasattr(job, 'fine_tuned_model') and job.fine_tuned_model:
                print(f"   微调后: {job.fine_tuned_model}")
            
            if hasattr(job, 'created_at'):
                print(f"   创建时间: {job.created_at}")
            
            print()
    
    except Exception as e:
        print(f"❌ 获取任务列表时出错: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='监控 DashScope 微调任务',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 监控指定任务
  python monitor_finetune.py <job_id>
  
  # 设置检查间隔
  python monitor_finetune.py <job_id> --interval 60
  
  # 列出所有任务
  python monitor_finetune.py --list
  
  # 使用指定 API Key
  python monitor_finetune.py <job_id> --api-key your-api-key
        """
    )
    
    parser.add_argument(
        'job_id',
        nargs='?',
        type=str,
        help='微调任务 ID'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='列出所有微调任务'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='检查间隔（秒，默认: 30）'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='DashScope API Key'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_jobs(args.api_key)
    elif args.job_id:
        monitor_job(args.job_id, args.interval, args.api_key)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

