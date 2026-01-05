#!/usr/bin/env python3
"""
DashScope 微调脚本 - 通过 DashScope API 进行模型微调
"""

import os
import sys
import time
import argparse
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import dashscope
    from dashscope import FineTunes, Files
except ImportError:
    print("❌ 错误: 未安装 dashscope SDK")
    print("请运行: pip3 install dashscope --user")
    print("或在虚拟环境中: pip install dashscope")
    sys.exit(1)


def safe_get(obj, key, default=None):
    """安全地从对象或字典中获取值"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    else:
        return getattr(obj, key, default)


class DashScopeFineTuner:
    """DashScope 微调管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化微调器
        
        Args:
            config: 配置字典
        """
        self.config = config
        
        # 设置 API Key
        api_key = config.get('api_key') or os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            raise ValueError("未设置 API Key，请在配置文件中设置或设置环境变量 DASHSCOPE_API_KEY")
        
        dashscope.api_key = api_key
        
        self.base_model = config.get('base_model', 'qwen-turbo')
        self.train_file = config.get('train_file')
        self.valid_file = config.get('valid_file')
        self.hyperparameters = config.get('hyperparameters', {})
        self.model_name = config.get('model_name', 'my-finetuned-model')
    
    def validate_files(self):
        """验证数据文件"""
        print("🔍 验证数据文件...")
        
        if not self.train_file:
            raise ValueError("未指定训练文件")
        
        train_path = Path(self.train_file)
        if not train_path.exists():
            raise FileNotFoundError(f"训练文件不存在: {train_path}")
        
        print(f"  ✅ 训练文件: {train_path} ({train_path.stat().st_size / 1024:.1f} KB)")
        
        if self.valid_file:
            valid_path = Path(self.valid_file)
            if not valid_path.exists():
                print(f"  ⚠️  验证文件不存在: {valid_path}，将只使用训练文件")
                self.valid_file = None
            else:
                print(f"  ✅ 验证文件: {valid_path} ({valid_path.stat().st_size / 1024:.1f} KB)")
    
    def create_finetune_job(self) -> str:
        """
        创建微调任务
        
        Returns:
            任务 ID
        """
        print(f"\n🚀 创建微调任务...")
        print(f"  基础模型: {self.base_model}")
        print(f"  模型名称: {self.model_name}")
        print(f"  训练文件: {self.train_file}")
        
        if self.valid_file:
            print(f"  验证文件: {self.valid_file}")
        
        print(f"  超参数:")
        for key, value in self.hyperparameters.items():
            print(f"    - {key}: {value}")
        
        try:
            # 第一步：上传训练文件
            print(f"\n📤 上传训练文件...")
            train_response = Files.upload(
                file_path=self.train_file,
                purpose='fine_tune',
                description=f"Training data for {self.model_name}"
            )
            
            if train_response.status_code != 200:
                print(f"❌ 上传训练文件失败: {train_response.message}")
                sys.exit(1)
            
            # 处理字典或对象两种可能的返回格式
            train_file_id = safe_get(train_response.output, 'id')
            print(f"✅ 训练文件上传成功: {train_file_id}")
            
            # 上传验证文件（如果有）
            valid_file_id = None
            if self.valid_file and Path(self.valid_file).exists():
                print(f"📤 上传验证文件...")
                valid_response = Files.upload(
                    file_path=self.valid_file,
                    purpose='fine_tune',
                    description=f"Validation data for {self.model_name}"
                )
                
                if valid_response.status_code == 200:
                    # 处理字典或对象两种可能的返回格式
                    valid_file_id = safe_get(valid_response.output, 'id')
                    print(f"✅ 验证文件上传成功: {valid_file_id}")
                else:
                    print(f"⚠️  验证文件上传失败（继续）: {valid_response.message}")
            
            # 第二步：创建微调任务
            print(f"\n🚀 创建微调任务...")
            response = FineTunes.call(
                model=self.base_model,
                training_file_ids=train_file_id,
                validation_file_ids=valid_file_id if valid_file_id else None,
                hyper_parameters=self.hyperparameters
            )
            
            if response.status_code == 200:
                # 处理字典或对象两种可能的返回格式
                job_id = safe_get(response.output, 'job_id') or safe_get(response.output, 'id')
                
                print(f"\n✅ 微调任务创建成功!")
                print(f"  任务 ID: {job_id}")
                print(f"  训练文件 ID: {train_file_id}")
                if valid_file_id:
                    print(f"  验证文件 ID: {valid_file_id}")
                return job_id
            else:
                print(f"\n❌ 创建任务失败:")
                print(f"  状态码: {response.status_code}")
                print(f"  错误信息: {response.message}")
                sys.exit(1)
        
        except Exception as e:
            print(f"\n❌ 创建任务时出错: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def monitor_job(self, job_id: str, check_interval: int = 30):
        """
        监控任务进度
        
        Args:
            job_id: 任务 ID
            check_interval: 检查间隔（秒）
        """
        print(f"\n📊 监控训练进度 (每 {check_interval} 秒检查一次)...")
        print("  提示: 按 Ctrl+C 可以退出监控（任务会继续运行）\n")
        
        last_status = None
        start_time = time.time()
        
        try:
            while True:
                response = FineTunes.get(job_id)
                
                if response.status_code != 200:
                    print(f"❌ 获取任务状态失败: {response.message}")
                    break
                
                # 安全地访问返回数据
                output = response.output
                status = safe_get(output, 'status')
                
                # 如果状态改变，显示更新
                if status != last_status:
                    elapsed = int(time.time() - start_time)
                    print(f"[{elapsed}s] 状态: {status}")
                    last_status = status
                
                # 检查是否完成
                if status == 'SUCCEEDED':
                    print(f"\n✅ 训练完成!")
                    
                    fine_tuned_model = safe_get(output, 'fine_tuned_model')
                    
                    print(f"\n📦 微调后的模型:")
                    print(f"  模型 ID: {fine_tuned_model}")
                    
                    # 显示训练指标
                    metrics = safe_get(output, 'metrics')
                    
                    if metrics:
                        print(f"\n📊 训练指标:")
                        if isinstance(metrics, dict):
                            for key, value in metrics.items():
                                print(f"  - {key}: {value}")
                        else:
                            print(f"  {metrics}")
                    
                    # 保存模型信息
                    self._save_model_info(job_id, fine_tuned_model)
                    
                    break
                
                elif status == 'FAILED':
                    print(f"\n❌ 训练失败!")
                    
                    error = safe_get(output, 'error')
                    if error:
                        print(f"  错误信息: {error}")
                    
                    break
                
                elif status == 'CANCELLED':
                    print(f"\n⚠️  训练已取消")
                    break
                
                # 等待下次检查
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            print(f"\n\n⚠️  监控已停止（任务仍在运行）")
            print(f"  任务 ID: {job_id}")
            print(f"  稍后可以使用以下命令继续监控:")
            print(f"  python scripts/monitor_finetune.py {job_id}")
    
    def _save_model_info(self, job_id: str, model_id: str):
        """保存模型信息"""
        output_dir = Path("output/models")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        info_file = output_dir / f"model_info_{job_id}.txt"
        
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write(f"任务 ID: {job_id}\n")
            f.write(f"模型 ID: {model_id}\n")
            f.write(f"基础模型: {self.base_model}\n")
            f.write(f"创建时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\n使用示例:\n")
            f.write(f"```python\n")
            f.write(f"from dashscope import Generation\n")
            f.write(f"import os\n\n")
            f.write(f"os.environ['DASHSCOPE_API_KEY'] = 'your-api-key'\n\n")
            f.write(f"response = Generation.call(\n")
            f.write(f"    model='{model_id}',\n")
            f.write(f"    prompt='你的问题',\n")
            f.write(f"    max_tokens=500\n")
            f.write(f")\n\n")
            f.write(f"print(response.output.text)\n")
            f.write(f"```\n")
        
        print(f"\n💾 模型信息已保存: {info_file}")


def load_config(config_file: str) -> Dict[str, Any]:
    """加载配置文件"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        if config_path.suffix in ['.yaml', '.yml']:
            config = yaml.safe_load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path.suffix}")
    
    return config


def main():
    parser = argparse.ArgumentParser(
        description='DashScope 模型微调工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用配置文件启动微调
  python dashscope_finetune.py config.yaml
  
  # 只创建任务，不监控
  python dashscope_finetune.py config.yaml --no-monitor
        """
    )
    
    parser.add_argument(
        'config_file',
        type=str,
        help='配置文件路径（YAML 格式）'
    )
    
    parser.add_argument(
        '--no-monitor',
        action='store_true',
        help='创建任务后不监控进度'
    )
    
    parser.add_argument(
        '--check-interval',
        type=int,
        default=30,
        help='监控检查间隔（秒，默认: 30）'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("DashScope 模型微调工具")
    print("="*60)
    
    # 加载配置
    print(f"\n📖 加载配置: {args.config_file}")
    
    try:
        config = load_config(args.config_file)
        print("✅ 配置加载成功")
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        sys.exit(1)
    
    # 创建微调器
    try:
        finetuner = DashScopeFineTuner(config)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 验证文件
    try:
        finetuner.validate_files()
    except Exception as e:
        print(f"❌ 文件验证失败: {e}")
        sys.exit(1)
    
    # 创建微调任务
    job_id = finetuner.create_finetune_job()
    
    # 监控任务
    if not args.no_monitor:
        finetuner.monitor_job(job_id, args.check_interval)
    else:
        print(f"\n提示: 使用以下命令监控任务:")
        print(f"  python scripts/monitor_finetune.py {job_id}")


if __name__ == '__main__':
    main()

