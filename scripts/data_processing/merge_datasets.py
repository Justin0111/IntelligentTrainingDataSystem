#!/usr/bin/env python3
"""
合并多个数据集文件
用于合并多次批量处理的结果
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict
import random


def load_jsonl(file_path: Path) -> List[Dict]:
    """加载 JSONL 文件"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def save_jsonl(data: List[Dict], file_path: Path):
    """保存为 JSONL 文件"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def deduplicate_data(data: List[Dict], key_fields: List[str]) -> List[Dict]:
    """
    根据指定字段去重
    
    Args:
        data: 数据列表
        key_fields: 用于去重的字段列表
        
    Returns:
        去重后的数据列表
    """
    seen = set()
    unique_data = []
    
    for item in data:
        # 构建唯一键
        key_parts = []
        for field in key_fields:
            value = item.get(field, "")
            if isinstance(value, str):
                key_parts.append(value[:100])  # 取前100字符
            else:
                key_parts.append(str(value))
        
        key = "||".join(key_parts)
        
        if key not in seen:
            seen.add(key)
            unique_data.append(item)
    
    return unique_data


def merge_datasets(
    input_files: List[Path],
    output_file: Path,
    deduplicate: bool = True,
    shuffle: bool = True,
    max_samples: int = None
):
    """
    合并多个数据集文件
    
    Args:
        input_files: 输入文件列表
        output_file: 输出文件路径
        deduplicate: 是否去重
        shuffle: 是否打乱
        max_samples: 最大样本数（可选）
    """
    print(f"正在合并 {len(input_files)} 个文件...")
    
    all_data = []
    stats = {}
    
    # 加载所有数据
    for file_path in input_files:
        if not file_path.exists():
            print(f"⚠️  文件不存在，跳过: {file_path}")
            continue
        
        print(f"  读取: {file_path.name}")
        data = load_jsonl(file_path)
        all_data.extend(data)
        stats[file_path.name] = len(data)
    
    original_count = len(all_data)
    print(f"\n原始数据总数: {original_count}")
    
    # 去重
    if deduplicate:
        # 判断数据类型（QA 或 Design）
        if all_data and 'question' in all_data[0]:
            # QA 数据
            all_data = deduplicate_data(all_data, ['question', 'answer'])
            print(f"QA 去重后: {len(all_data)} (移除 {original_count - len(all_data)})")
        elif all_data and 'requirement' in all_data[0]:
            # Design 数据
            all_data = deduplicate_data(all_data, ['requirement'])
            print(f"Design 去重后: {len(all_data)} (移除 {original_count - len(all_data)})")
        else:
            print("⚠️  无法识别数据类型，跳过去重")
    
    # 限制数量
    if max_samples and len(all_data) > max_samples:
        all_data = random.sample(all_data, max_samples)
        print(f"随机采样到: {max_samples}")
    
    # 打乱
    if shuffle:
        random.shuffle(all_data)
        print("数据已打乱")
    
    # 保存
    save_jsonl(all_data, output_file)
    print(f"\n✅ 合并完成！")
    print(f"输出文件: {output_file}")
    print(f"最终数据量: {len(all_data)}")
    
    # 显示统计
    print("\n各文件贡献:")
    for filename, count in stats.items():
        percentage = count / original_count * 100 if original_count > 0 else 0
        print(f"  {filename}: {count} ({percentage:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="合并多个训练数据集文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 合并多个 QA 数据集
  python merge_datasets.py output/batch1/qa_dataset.jsonl output/batch2/qa_dataset.jsonl -o merged_qa.jsonl
  
  # 合并并限制最大数量
  python merge_datasets.py data/*.jsonl -o final.jsonl --max-samples 1000
  
  # 合并但不去重
  python merge_datasets.py batch1/*.jsonl -o output.jsonl --no-deduplicate
        """
    )
    
    parser.add_argument(
        'input_files',
        nargs='+',
        type=Path,
        help='输入文件列表（支持通配符）'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help='输出文件路径'
    )
    parser.add_argument(
        '--no-deduplicate',
        action='store_true',
        help='不进行去重'
    )
    parser.add_argument(
        '--no-shuffle',
        action='store_true',
        help='不打乱数据'
    )
    parser.add_argument(
        '--max-samples',
        type=int,
        help='限制最大样本数'
    )
    
    args = parser.parse_args()
    
    # 展开通配符
    input_files = []
    for pattern in args.input_files:
        if '*' in str(pattern) or '?' in str(pattern):
            # 通配符
            parent = pattern.parent if pattern.parent.exists() else Path('.')
            matched = list(parent.glob(pattern.name))
            input_files.extend(matched)
        else:
            input_files.append(pattern)
    
    if not input_files:
        print("❌ 错误: 没有找到输入文件")
        return
    
    # 去重文件列表
    input_files = list(set(input_files))
    
    merge_datasets(
        input_files=input_files,
        output_file=args.output,
        deduplicate=not args.no_deduplicate,
        shuffle=not args.no_shuffle,
        max_samples=args.max_samples
    )


if __name__ == "__main__":
    main()

