#!/usr/bin/env python3
"""
数据集划分脚本
将单个数据集文件按比例划分为 train/valid/test 集
"""

import json
import argparse
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple
import sys


def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """加载 JSONL 文件"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"⚠️  第 {line_num} 行解析错误: {e}")
    return data


def save_jsonl(data: List[Dict[str, Any]], file_path: Path):
    """保存为 JSONL 文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def split_dataset(
    data: List[Dict[str, Any]],
    train_ratio: float = 0.8,
    valid_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    划分数据集
    
    Args:
        data: 原始数据
        train_ratio: 训练集比例
        valid_ratio: 验证集比例
        test_ratio: 测试集比例
        seed: 随机种子
        
    Returns:
        (训练集, 验证集, 测试集)
    """
    # 检查比例
    total_ratio = train_ratio + valid_ratio + test_ratio
    if abs(total_ratio - 1.0) > 0.001:
        raise ValueError(f"比例之和必须为 1.0，当前为 {total_ratio}")
    
    # 设置随机种子
    random.seed(seed)
    
    # 打乱数据
    shuffled_data = data.copy()
    random.shuffle(shuffled_data)
    
    # 计算划分点
    total = len(shuffled_data)
    train_end = int(total * train_ratio)
    valid_end = train_end + int(total * valid_ratio)
    
    # 划分数据
    train_data = shuffled_data[:train_end]
    valid_data = shuffled_data[train_end:valid_end]
    test_data = shuffled_data[valid_end:]
    
    return train_data, valid_data, test_data


def main():
    parser = argparse.ArgumentParser(
        description='将数据集划分为 train/valid/test 集',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 按 8:1:1 划分（默认）
  python split_dataset.py input.alpaca -o output_dir
  
  # 自定义比例（8:1.5:0.5）
  python split_dataset.py input.alpaca -o output_dir \
      --train-ratio 0.8 --valid-ratio 0.15 --test-ratio 0.05
  
  # 按 9:1:0 划分（不要测试集）
  python split_dataset.py input.alpaca -o output_dir \
      --train-ratio 0.9 --valid-ratio 0.1 --test-ratio 0
        """
    )
    
    parser.add_argument(
        'input_file',
        type=str,
        help='输入文件路径（JSONL 格式）'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        help='输出目录（默认：输入文件所在目录）'
    )
    
    parser.add_argument(
        '--train-ratio',
        type=float,
        default=0.8,
        help='训练集比例（默认: 0.8）'
    )
    
    parser.add_argument(
        '--valid-ratio',
        type=float,
        default=0.1,
        help='验证集比例（默认: 0.1）'
    )
    
    parser.add_argument(
        '--test-ratio',
        type=float,
        default=0.1,
        help='测试集比例（默认: 0.1）'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='随机种子（默认: 42）'
    )
    
    parser.add_argument(
        '--output-prefix',
        type=str,
        help='输出文件名前缀（默认：使用输入文件名）'
    )
    
    args = parser.parse_args()
    
    # 检查输入文件
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ 错误: 输入文件不存在: {input_path}")
        sys.exit(1)
    
    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 确定输出文件名前缀
    if args.output_prefix:
        output_prefix = args.output_prefix
    else:
        output_prefix = input_path.stem
    
    print("="*60)
    print("数据集划分工具")
    print("="*60)
    print()
    
    # 加载数据
    print(f"📖 加载数据: {input_path}")
    try:
        data = load_jsonl(input_path)
        print(f"✅ 成功加载 {len(data)} 条数据")
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        sys.exit(1)
    
    if len(data) == 0:
        print("❌ 错误: 数据文件为空")
        sys.exit(1)
    
    # 划分数据
    print()
    print("🔀 划分数据集...")
    print(f"  比例: 训练 {args.train_ratio:.1%} | 验证 {args.valid_ratio:.1%} | 测试 {args.test_ratio:.1%}")
    print(f"  随机种子: {args.seed}")
    
    try:
        train_data, valid_data, test_data = split_dataset(
            data,
            train_ratio=args.train_ratio,
            valid_ratio=args.valid_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed
        )
    except ValueError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)
    
    print(f"✅ 划分完成")
    print(f"  - 训练集: {len(train_data)} 条 ({len(train_data)/len(data):.1%})")
    print(f"  - 验证集: {len(valid_data)} 条 ({len(valid_data)/len(data):.1%})")
    print(f"  - 测试集: {len(test_data)} 条 ({len(test_data)/len(data):.1%})")
    
    # 保存数据
    print()
    print("💾 保存划分后的数据...")
    
    # 训练集
    if len(train_data) > 0:
        train_path = output_dir / f"{output_prefix}_train.alpaca"
        save_jsonl(train_data, train_path)
        print(f"  ✅ 训练集: {train_path} ({len(train_data)} 条)")
    
    # 验证集
    if len(valid_data) > 0:
        valid_path = output_dir / f"{output_prefix}_valid.alpaca"
        save_jsonl(valid_data, valid_path)
        print(f"  ✅ 验证集: {valid_path} ({len(valid_data)} 条)")
    
    # 测试集
    if len(test_data) > 0:
        test_path = output_dir / f"{output_prefix}_test.alpaca"
        save_jsonl(test_data, test_path)
        print(f"  ✅ 测试集: {test_path} ({len(test_data)} 条)")
    
    print()
    print("="*60)
    print("✅ 完成!")
    print("="*60)
    print()
    print("输出文件:")
    print(f"  - {output_dir / f'{output_prefix}_train.alpaca'}")
    print(f"  - {output_dir / f'{output_prefix}_valid.alpaca'}")
    print(f"  - {output_dir / f'{output_prefix}_test.alpaca'}")
    print()
    print("下一步:")
    print("  1. 验证划分后的数据")
    print("  2. 使用快速开始脚本进行微调:")
    print("     python scripts/quickstart_finetune.py")


if __name__ == '__main__':
    main()

