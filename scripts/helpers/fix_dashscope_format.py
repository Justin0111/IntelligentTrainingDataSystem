#!/usr/bin/env python3
"""
修复 dashscope JSONL 格式
移除 errorCode 和 errorLineNum 字段，只保留 prompt 和 response
"""

import json
import sys
from pathlib import Path


def fix_jsonl_format(input_file: str, output_file: str = None):
    """
    修复 JSONL 文件格式，移除不需要的字段
    
    Args:
        input_file: 输入的 JSONL 文件路径
        output_file: 输出的 JSONL 文件路径（可选，默认为 input_file 加 _fixed 后缀）
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"❌ 错误：文件不存在: {input_file}")
        return False
    
    # 如果没有指定输出文件，使用默认命名
    if output_file is None:
        output_file = str(input_path.parent / f"{input_path.stem}_fixed{input_path.suffix}")
    
    output_path = Path(output_file)
    
    print(f"📖 读取文件: {input_file}")
    
    fixed_count = 0
    total_count = 0
    
    try:
        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', encoding='utf-8') as outfile:
            
            for line_num, line in enumerate(infile, 1):
                total_count += 1
                line = line.strip()
                
                if not line:
                    continue
                
                try:
                    # 解析 JSON
                    data = json.loads(line)
                    
                    # 检查是否包含必需字段
                    if 'prompt' not in data or 'response' not in data:
                        print(f"⚠️  警告：第 {line_num} 行缺少必需字段（prompt 或 response），跳过")
                        continue
                    
                    # 只保留 prompt 和 response 字段
                    cleaned_data = {
                        'prompt': data['prompt'],
                        'response': data['response']
                    }
                    
                    # 写入清理后的数据
                    outfile.write(json.dumps(cleaned_data, ensure_ascii=False) + '\n')
                    fixed_count += 1
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  警告：第 {line_num} 行 JSON 解析失败: {e}")
                    continue
        
        print(f"\n✅ 修复完成！")
        print(f"   - 总行数: {total_count}")
        print(f"   - 成功修复: {fixed_count}")
        print(f"   - 输出文件: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误：处理文件时发生异常: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: python fix_dashscope_format.py <input_file> [output_file]")
        print("\n示例:")
        print("  python fix_dashscope_format.py data.jsonl")
        print("  python fix_dashscope_format.py data.jsonl output.jsonl")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = fix_jsonl_format(input_file, output_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

