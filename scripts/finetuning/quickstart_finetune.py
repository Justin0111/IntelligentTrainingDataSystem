#!/usr/bin/env python3
"""
DashScope 微调快速开始脚本 (Python 版本)
一键完成数据转换、验证、配置和微调
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import glob


class Colors:
    """终端颜色"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.NC}")


def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.NC}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.NC}")


def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.NC}")


def print_header(msg: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}{msg}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}\n")


def run_command(cmd: list, description: str = "") -> Tuple[int, str, str]:
    """
    运行命令并返回结果
    
    Returns:
        (返回码, 标准输出, 标准错误)
    """
    if description:
        print_info(description)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def check_dependencies() -> bool:
    """检查依赖"""
    print_header("检查依赖")
    
    # 检查 Python
    print_success(f"Python: {sys.version.split()[0]}")
    
    # 检查 dashscope
    try:
        import dashscope
        print_success(f"dashscope SDK 已安装")
    except ImportError:
        print_error("未安装 dashscope SDK")
        print_info("请运行: pip3 install dashscope --user")
        return False
    
    # 检查 PyYAML
    try:
        import yaml
        print_success("PyYAML 已安装")
    except ImportError:
        print_error("未安装 PyYAML")
        print_info("请运行: pip3 install pyyaml --user")
        return False
    
    return True


def check_api_key() -> Optional[str]:
    """检查 API Key"""
    print_header("检查 API Key")
    
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    
    if not api_key:
        # 尝试从 .env 文件读取
        env_file = Path('.env')
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('DASHSCOPE_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"\'')
                        break
    
    if not api_key:
        print_error("未设置 DASHSCOPE_API_KEY")
        print()
        print("请设置环境变量:")
        print("  export DASHSCOPE_API_KEY='your-api-key'")
        print()
        print("或在 .env 文件中添加:")
        print("  DASHSCOPE_API_KEY=your-api-key")
        return None
    
    print_success("API Key 已设置")
    return api_key


def find_training_data() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """查找训练数据"""
    print_header("查找训练数据")
    
    # 查找最新的 QA 训练数据
    qa_train_files = sorted(
        glob.glob('output/complete_training/merged_qa_dataset_*_train.alpaca'),
        key=os.path.getmtime,
        reverse=True
    )
    
    qa_valid_files = sorted(
        glob.glob('output/complete_training/merged_qa_dataset_*_valid.alpaca'),
        key=os.path.getmtime,
        reverse=True
    )
    
    qa_test_files = sorted(
        glob.glob('output/complete_training/merged_qa_dataset_*_test.alpaca'),
        key=os.path.getmtime,
        reverse=True
    )
    
    # 查找最新的 Design 训练数据
    design_train_files = sorted(
        glob.glob('output/complete_training/merged_design_dataset_*.alpaca'),
        key=os.path.getmtime,
        reverse=True
    )
    
    if not qa_train_files:
        print_error("未找到 QA 训练数据文件")
        print()
        print("请先生成训练数据:")
        print("  python main.py batch-generate <repos_file> -o output/complete_training --split")
        return None, None, None
    
    qa_train_file = qa_train_files[0]
    qa_valid_file = qa_valid_files[0] if qa_valid_files else None
    qa_test_file = qa_test_files[0] if qa_test_files else None
    design_train_file = design_train_files[0] if design_train_files else None
    
    print_success(f"QA 训练数据: {qa_train_file}")
    with open(qa_train_file, 'r') as f:
        qa_count = sum(1 for line in f if line.strip())
    print_info(f"  QA 样本数: {qa_count}")
    
    if design_train_file:
        print_success(f"Design 数据: {design_train_file}")
        with open(design_train_file, 'r') as f:
            design_count = sum(1 for line in f if line.strip())
        print_info(f"  Design 样本数: {design_count}")
    else:
        print_warning("未找到 Design 数据文件")
    
    if qa_valid_file:
        print_success(f"验证数据: {qa_valid_file}")
    
    if qa_test_file:
        print_success(f"测试数据: {qa_test_file}")
    
    return qa_train_file, qa_valid_file, qa_test_file


def merge_qa_design_data() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """合并 QA 和 Design 数据（分别合并 train/valid/test）"""
    print_header("合并 QA 和 Design 数据")
    
    # 查找 QA 数据文件
    qa_files = sorted(
        glob.glob('output/complete_training/merged_qa_dataset_*.alpaca'),
        key=os.path.getmtime,
        reverse=True
    )
    
    if not qa_files:
        print_error("未找到 QA 数据文件")
        return None, None, None
    
    # 显示找到的 QA 数据
    qa_base = qa_files[0].replace('_train.alpaca', '').replace('_valid.alpaca', '').replace('_test.alpaca', '').replace('.alpaca', '')
    print_success("找到 QA 数据")
    
    splits = ['train', 'valid', 'test']
    total_qa_count = 0
    found_qa_splits = []
    
    for split in splits:
        split_file = f"{qa_base}_{split}.alpaca"
        if Path(split_file).exists():
            with open(split_file, 'r') as f:
                count = sum(1 for line in f if line.strip())
            print_info(f"  {split}: {count} 条 ({Path(split_file).name})")
            total_qa_count += count
            found_qa_splits.append(split)
    
    if found_qa_splits:
        print_info(f"  总计: {total_qa_count} 条 QA 数据（{len(found_qa_splits)} 个数据集）")
    print()
    
    # 查找 Design 数据文件（在多个可能的目录中查找）
    design_search_paths = [
        'output/complete_training/merged_design_dataset_*.alpaca',
        'output/design_supplement/merged_design_dataset_*.alpaca',
        'output/*/merged_design_dataset_*.alpaca',  # 通配符查找
    ]
    
    design_files = []
    for search_path in design_search_paths:
        found_files = glob.glob(search_path)
        design_files.extend(found_files)
    
    # 去重并按修改时间排序
    design_files = list(set(design_files))
    design_files = sorted(design_files, key=os.path.getmtime, reverse=True)
    
    if design_files:
        # 提取 design 基础文件名（去除 _train/_valid/_test 和 .alpaca 后缀）
        design_base = design_files[0].replace('_train.alpaca', '').replace('_valid.alpaca', '').replace('_test.alpaca', '').replace('.alpaca', '')
        
        # 显示找到的 Design 数据位置
        design_dir = str(Path(design_files[0]).parent)
        print_success(f"找到 Design 数据")
        print_info(f"  位置: {design_dir}")
        
        # 查找并统计所有三个数据集（train/valid/test）
        splits = ['train', 'valid', 'test']
        total_design_count = 0
        found_splits = []
        
        for split in splits:
            split_file = f"{design_base}_{split}.alpaca"
            if Path(split_file).exists():
                with open(split_file, 'r') as f:
                    count = sum(1 for line in f if line.strip())
                print_info(f"  {split}: {count} 条 ({Path(split_file).name})")
                total_design_count += count
                found_splits.append(split)
        
        if found_splits:
            print_info(f"  总计: {total_design_count} 条 Design 数据（{len(found_splits)} 个数据集）")
        
        print_info("发现 QA 和 Design 数据，将分别合并 train/valid/test 三个数据集")
        response = input("是否合并 QA 和 Design 数据? (Y/n): ").strip().lower()
        
        if response in ['', 'y', 'yes']:
            # 合并数据
            output_base = 'output/merged/merged_all_dataset'
            
            print_info("合并数据中...")
            returncode = subprocess.call([
                sys.executable, 'scripts/merge_qa_design.py',
                '--qa-base', qa_base,
                '--design-base', design_base,
                '--output-base', output_base,
                '--all-splits',
                '--qa-ratio', '0.7'
            ])
            
            if returncode == 0:
                print_success("数据合并完成！")
                print_info("已生成以下合并数据集：")
                
                train_file = f"{output_base}_train.alpaca"
                valid_file = f"{output_base}_valid.alpaca" if Path(f"{output_base}_valid.alpaca").exists() else None
                test_file = f"{output_base}_test.alpaca" if Path(f"{output_base}_test.alpaca").exists() else None
                
                # 显示每个文件的样本数
                if Path(train_file).exists():
                    with open(train_file, 'r') as f:
                        count = sum(1 for line in f if line.strip())
                    print_info(f"  train: {count} 条 ({Path(train_file).name})")
                
                if valid_file and Path(valid_file).exists():
                    with open(valid_file, 'r') as f:
                        count = sum(1 for line in f if line.strip())
                    print_info(f"  valid: {count} 条 ({Path(valid_file).name})")
                
                if test_file and Path(test_file).exists():
                    with open(test_file, 'r') as f:
                        count = sum(1 for line in f if line.strip())
                    print_info(f"  test: {count} 条 ({Path(test_file).name})")
                
                print()
                return (train_file, valid_file, test_file)
            else:
                print_warning("合并失败，将只使用 QA 数据")
        else:
            print_info("跳过合并，只使用 QA 数据")
    else:
        print_info("只找到 QA 数据")
    
    # 返回 QA 数据
    train_file = next((f for f in qa_files if '_train.alpaca' in f), None)
    valid_file = next((f for f in qa_files if '_valid.alpaca' in f), None)
    test_file = next((f for f in qa_files if '_test.alpaca' in f), None)
    
    return train_file, valid_file, test_file


def convert_data(train_file: str, valid_file: Optional[str], test_file: Optional[str]) -> bool:
    """转换数据格式"""
    print_header("转换数据格式")
    
    # 创建输出目录
    Path('output/dashscope').mkdir(parents=True, exist_ok=True)
    
    # 转换训练集
    print_info("转换训练集...")
    returncode, stdout, stderr = run_command([
        sys.executable, 'scripts/convert_to_dashscope.py',
        train_file,
        '-o', 'output/dashscope/train.jsonl',
        '--format', 'prompt-response'
    ])
    
    if returncode != 0:
        print_error("转换训练集失败")
        print(stderr)
        return False
    
    print_success("训练集转换完成")
    
    # 转换验证集
    if valid_file:
        print_info("转换验证集...")
        returncode, _, stderr = run_command([
            sys.executable, 'scripts/convert_to_dashscope.py',
            valid_file,
            '-o', 'output/dashscope/valid.jsonl',
            '--format', 'prompt-response'
        ])
        
        if returncode != 0:
            print_warning("转换验证集失败（继续）")
        else:
            print_success("验证集转换完成")
    
    # 转换测试集
    if test_file:
        print_info("转换测试集...")
        returncode, _, stderr = run_command([
            sys.executable, 'scripts/convert_to_dashscope.py',
            test_file,
            '-o', 'output/dashscope/test.jsonl',
            '--format', 'prompt-response'
        ])
        
        if returncode != 0:
            print_warning("转换测试集失败（继续）")
        else:
            print_success("测试集转换完成")
    
    return True


def validate_data() -> bool:
    """验证数据"""
    print_header("验证数据格式")
    
    print_info("验证训练数据...")
    returncode, stdout, stderr = run_command([
        sys.executable, 'scripts/validate_dashscope_data.py',
        'output/dashscope/train.jsonl'
    ])
    
    # 显示输出
    if stdout:
        print(stdout)
    
    if returncode != 0:
        print_error("数据验证失败")
        if stderr:
            print(stderr)
        return False
    
    print_success("数据验证通过")
    return True


def create_config(api_key: str) -> bool:
    """创建配置文件"""
    print_header("创建配置文件")
    
    config_file = Path('scripts/finetune_config.yaml')
    
    if config_file.exists():
        print_warning(f"配置文件已存在: {config_file}")
        response = input("是否覆盖? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print_info("使用现有配置文件")
            return True
    
    # 创建配置文件
    from datetime import datetime
    model_name = f"qwen-turbo-code-{datetime.now().strftime('%Y%m%d')}"
    
    config_content = f"""# DashScope 微调配置文件
api_key: "{api_key}"

base_model: "qwen-turbo"
model_name: "{model_name}"

train_file: "output/dashscope/train.jsonl"
valid_file: "output/dashscope/valid.jsonl"

hyperparameters:
  epochs: 3
  batch_size: 16
  learning_rate: 2e-5
"""
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        print_success(f"配置文件已创建: {config_file}")
        return True
    except Exception as e:
        print_error(f"创建配置文件失败: {e}")
        return False


def start_finetune() -> bool:
    """开始微调"""
    print_header("开始微调")
    
    print_info("使用配置: scripts/finetune_config.yaml")
    print_warning("即将开始微调，这将产生费用")
    
    response = input("是否继续? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print_info("已取消")
        return False
    
    print_info("启动微调任务...")
    
    # 注意：这里直接运行微调脚本，输出会直接显示
    returncode = subprocess.call([
        sys.executable, 'scripts/dashscope_finetune.py',
        'scripts/finetune_config.yaml'
    ])
    
    return returncode == 0


def main():
    """主函数"""
    print_header("DashScope 微调快速开始")
    
    # 1. 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 2. 检查 API Key
    api_key = check_api_key()
    if not api_key:
        sys.exit(1)
    
    # 3. 查找并合并训练数据
    train_file, valid_file, test_file = merge_qa_design_data()
    if not train_file:
        sys.exit(1)
    
    # 4. 转换数据格式
    if not convert_data(train_file, valid_file, test_file):
        sys.exit(1)
    
    # 5. 验证数据
    if not validate_data():
        print_warning("数据验证有问题，但可以继续")
        response = input("是否继续? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print_info("已取消")
            sys.exit(1)
    
    # 6. 创建配置文件
    if not create_config(api_key):
        sys.exit(1)
    
    # 7. 开始微调
    if not start_finetune():
        print_error("微调启动失败")
        sys.exit(1)
    
    # 完成
    print_header("完成")
    print_success("微调任务已启动")
    print()
    print("下一步:")
    print("  1. 等待训练完成（约 20-60 分钟）")
    print("  2. 使用微调后的模型进行推理")
    print("  3. 评估模型效果:")
    print("     python scripts/evaluate_finetuned_model.py \\")
    print("         --model <model_id> \\")
    print("         --test-file output/dashscope/test.jsonl")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_warning("用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

