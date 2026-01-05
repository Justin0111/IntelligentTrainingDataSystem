#!/usr/bin/env python3
"""
合并 QA 和 Design 数据集
用于微调时将两种数据混合训练
"""

import json
import argparse
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
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


def balance_datasets(
    qa_data: List[Dict[str, Any]],
    design_data: List[Dict[str, Any]],
    qa_ratio: float = 0.7
) -> tuple:
    """
    平衡两个数据集的比例
    
    Args:
        qa_data: QA 数据
        design_data: Design 数据
        qa_ratio: QA 数据的目标比例 (0-1)
        
    Returns:
        (平衡后的 QA 数据, 平衡后的 Design 数据)
    """
    total_qa = len(qa_data)
    total_design = len(design_data)
    
    if total_qa == 0 or total_design == 0:
        return qa_data, design_data
    
    # 计算当前比例
    current_ratio = total_qa / (total_qa + total_design)
    
    print(f"当前比例: QA={total_qa} ({current_ratio:.1%}), Design={total_design} ({1-current_ratio:.1%})")
    print(f"目标比例: QA={qa_ratio:.1%}, Design={1-qa_ratio:.1%}")
    
    # 如果差异不大（5%以内），不需要平衡
    if abs(current_ratio - qa_ratio) < 0.05:
        print("✅ 数据比例已接近目标，无需调整")
        return qa_data, design_data
    
    # 计算目标数量
    if current_ratio > qa_ratio:
        # QA 数据过多，需要减少
        target_qa = int(total_design * qa_ratio / (1 - qa_ratio))
        if target_qa < total_qa:
            print(f"⚖️  调整 QA 数据量: {total_qa} -> {target_qa}")
            qa_data = random.sample(qa_data, target_qa)
    else:
        # Design 数据过多，需要减少
        target_design = int(total_qa * (1 - qa_ratio) / qa_ratio)
        if target_design < total_design:
            print(f"⚖️  调整 Design 数据量: {total_design} -> {target_design}")
            design_data = random.sample(design_data, target_design)
    
    return qa_data, design_data


def merge_datasets(
    qa_file: str,
    design_file: str,
    output_file: str,
    qa_ratio: float = 0.7,
    shuffle: bool = True,
    balance: bool = True,
    max_samples: Optional[int] = None
):
    """
    合并 QA 和 Design 数据集
    
    Args:
        qa_file: QA 数据文件路径
        design_file: Design 数据文件路径
        output_file: 输出文件路径
        qa_ratio: QA 数据的目标比例
        shuffle: 是否打乱数据
        balance: 是否平衡数据比例
        max_samples: 最大样本数（限制总数）
    """
    print("="*60)
    print("合并 QA 和 Design 数据集")
    print("="*60)
    
    # 加载数据
    print(f"\n📖 加载 QA 数据: {qa_file}")
    qa_data = load_jsonl(Path(qa_file))
    print(f"✅ 加载 {len(qa_data)} 条 QA 数据")
    
    print(f"\n📖 加载 Design 数据: {design_file}")
    design_data = load_jsonl(Path(design_file))
    print(f"✅ 加载 {len(design_data)} 条 Design 数据")
    
    if not qa_data and not design_data:
        print("❌ 错误: 没有数据可合并")
        return
    
    # 平衡数据
    if balance and qa_data and design_data:
        print(f"\n⚖️  平衡数据比例...")
        qa_data, design_data = balance_datasets(qa_data, design_data, qa_ratio)
    
    # 合并数据
    print(f"\n🔗 合并数据...")
    merged_data = qa_data + design_data
    
    # 限制总数
    if max_samples and len(merged_data) > max_samples:
        print(f"📏 限制总样本数: {len(merged_data)} -> {max_samples}")
        # 按比例采样
        qa_count = int(max_samples * qa_ratio)
        design_count = max_samples - qa_count
        
        qa_data = random.sample(qa_data, min(qa_count, len(qa_data)))
        design_data = random.sample(design_data, min(design_count, len(design_data)))
        
        merged_data = qa_data + design_data
    
    # 打乱数据
    if shuffle:
        print(f"🔀 打乱数据...")
        random.shuffle(merged_data)
    
    # 保存数据
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 保存合并数据: {output_path}")
    save_jsonl(merged_data, output_path)
    
    # 统计信息
    final_qa = len(qa_data)
    final_design = len(design_data)
    final_total = len(merged_data)
    final_ratio = final_qa / final_total if final_total > 0 else 0
    
    print(f"\n{'='*60}")
    print("📊 合并完成")
    print(f"{'='*60}")
    print(f"QA 数据: {final_qa} ({final_ratio:.1%})")
    print(f"Design 数据: {final_design} ({1-final_ratio:.1%})")
    print(f"总计: {final_total}")
    print(f"输出: {output_path}")
    print()
    
    # 显示示例
    if merged_data:
        print("📝 数据示例（前 2 条）:")
        for i, item in enumerate(merged_data[:2], 1):
            print(f"\n--- 示例 {i} ---")
            print(f"Instruction: {item.get('instruction', '')[:100]}...")
            if item.get('input'):
                print(f"Input: {item.get('input', '')[:100]}...")
            print(f"Output: {item.get('output', '')[:100]}...")


def merge_splits(
    qa_base: str,
    design_base: str,
    output_base: str,
    qa_ratio: float = 0.7,
    shuffle: bool = True,
    balance: bool = True
):
    """
    合并训练/验证/测试集的所有划分
    
    Args:
        qa_base: QA 数据文件基础路径（不含 _train/_valid/_test 后缀）
        design_base: Design 数据文件基础路径
        output_base: 输出文件基础路径
        qa_ratio: QA 数据的目标比例
        shuffle: 是否打乱数据
        balance: 是否平衡数据比例
    """
    splits = ['train', 'valid', 'test']
    
    for split in splits:
        qa_file = f"{qa_base}_{split}.alpaca"
        design_file = f"{design_base}_{split}.alpaca"
        output_file = f"{output_base}_{split}.alpaca"
        
        # 检查文件是否存在
        if not Path(qa_file).exists():
            print(f"⚠️  跳过 {split}: QA 文件不存在 ({qa_file})")
            continue
        
        if not Path(design_file).exists():
            print(f"⚠️  跳过 {split}: Design 文件不存在 ({design_file})")
            continue
        
        print(f"\n{'='*60}")
        print(f"处理 {split.upper()} 集")
        print(f"{'='*60}")
        
        merge_datasets(
            qa_file,
            design_file,
            output_file,
            qa_ratio=qa_ratio,
            shuffle=shuffle,
            balance=balance
        )


def main():
    parser = argparse.ArgumentParser(
        description='合并 QA 和 Design 数据集，用于微调训练',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 合并单个文件
  python merge_qa_design.py \
      --qa merged_qa_dataset_20260105_train.alpaca \
      --design merged_design_dataset_20260105_train.alpaca \
      -o merged_all_train.alpaca
  
  # 合并所有划分（train/valid/test）
  python merge_qa_design.py \
      --qa-base output/complete_training/merged_qa_dataset_20260105 \
      --design-base output/complete_training/merged_design_dataset_20260105 \
      --output-base output/merged/merged_all_20260105 \
      --all-splits
  
  # 调整比例
  python merge_qa_design.py \
      --qa qa_train.alpaca \
      --design design_train.alpaca \
      -o merged_train.alpaca \
      --qa-ratio 0.8  # 80% QA, 20% Design
  
  # 不平衡数据（保持原始比例）
  python merge_qa_design.py \
      --qa qa_train.alpaca \
      --design design_train.alpaca \
      -o merged_train.alpaca \
      --no-balance
        """
    )
    
    parser.add_argument(
        '--qa',
        type=str,
        help='QA 数据文件路径'
    )
    
    parser.add_argument(
        '--design',
        type=str,
        help='Design 数据文件路径'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='输出文件路径'
    )
    
    parser.add_argument(
        '--qa-base',
        type=str,
        help='QA 数据文件基础路径（用于 --all-splits）'
    )
    
    parser.add_argument(
        '--design-base',
        type=str,
        help='Design 数据文件基础路径（用于 --all-splits）'
    )
    
    parser.add_argument(
        '--output-base',
        type=str,
        help='输出文件基础路径（用于 --all-splits）'
    )
    
    parser.add_argument(
        '--all-splits',
        action='store_true',
        help='合并所有划分（train/valid/test）'
    )
    
    parser.add_argument(
        '--qa-ratio',
        type=float,
        default=0.7,
        help='QA 数据的目标比例（0-1，默认: 0.7）'
    )
    
    parser.add_argument(
        '--no-shuffle',
        action='store_true',
        help='不打乱数据顺序'
    )
    
    parser.add_argument(
        '--no-balance',
        action='store_true',
        help='不平衡数据比例'
    )
    
    parser.add_argument(
        '--max-samples',
        type=int,
        help='最大样本数（限制总数）'
    )
    
    args = parser.parse_args()
    
    # 设置随机种子以保证可重复性
    random.seed(42)
    
    if args.all_splits:
        # 合并所有划分
        if not args.qa_base or not args.design_base or not args.output_base:
            print("❌ 错误: 使用 --all-splits 时需要指定 --qa-base, --design-base 和 --output-base")
            sys.exit(1)
        
        merge_splits(
            args.qa_base,
            args.design_base,
            args.output_base,
            qa_ratio=args.qa_ratio,
            shuffle=not args.no_shuffle,
            balance=not args.no_balance
        )
    else:
        # 合并单个文件
        if not args.qa or not args.design or not args.output:
            print("❌ 错误: 需要指定 --qa, --design 和 --output")
            parser.print_help()
            sys.exit(1)
        
        merge_datasets(
            args.qa,
            args.design,
            args.output,
            qa_ratio=args.qa_ratio,
            shuffle=not args.no_shuffle,
            balance=not args.no_balance,
            max_samples=args.max_samples
        )


if __name__ == '__main__':
    main()

