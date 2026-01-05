#!/usr/bin/env python3
"""
将 prompt/response 格式转换为 messages 格式（ChatML）
DashScope 微调需要使用 messages 格式
"""

import json
import sys
from pathlib import Path
from typing import Dict, List


def convert_to_messages_format(item: Dict) -> Dict:
    """
    将 prompt/response 格式转换为 messages 格式
    
    Args:
        item: 包含 prompt 和 response 的字典
        
    Returns:
        包含 messages 的字典
    """
    prompt = item.get("prompt", "")
    response = item.get("response", "")
    
    if not prompt or not response:
        raise ValueError("数据必须包含 prompt 和 response 字段")
    
    # 构建 messages 格式
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的代码分析助手，能够准确理解代码并提供详细的解释。"
        },
        {
            "role": "user",
            "content": prompt
        },
        {
            "role": "assistant",
            "content": response
        }
    ]
    
    return {"messages": messages}


def convert_file(input_file: str, output_file: str = None):
    """
    转换整个 JSONL 文件
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径（可选）
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"❌ 错误：文件不存在: {input_file}")
        return False
    
    # 如果没有指定输出文件，使用默认命名
    if output_file is None:
        output_file = str(input_path.parent / f"{input_path.stem}_messages{input_path.suffix}")
    
    output_path = Path(output_file)
    
    print(f"📖 读取文件: {input_file}")
    
    converted_count = 0
    error_count = 0
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
                    
                    # 转换为 messages 格式
                    converted_data = convert_to_messages_format(data)
                    
                    # 写入转换后的数据
                    outfile.write(json.dumps(converted_data, ensure_ascii=False) + '\n')
                    converted_count += 1
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  警告：第 {line_num} 行 JSON 解析失败: {e}")
                    error_count += 1
                except ValueError as e:
                    print(f"⚠️  警告：第 {line_num} 行数据格式错误: {e}")
                    error_count += 1
                except Exception as e:
                    print(f"⚠️  警告：第 {line_num} 行处理失败: {e}")
                    error_count += 1
        
        print(f"\n✅ 转换完成！")
        print(f"   - 总行数: {total_count}")
        print(f"   - 成功转换: {converted_count}")
        print(f"   - 失败: {error_count}")
        print(f"   - 输出文件: {output_file}")
        
        # 显示示例
        if converted_count > 0:
            print(f"\n📝 格式示例（前 1 行）：")
            with open(output_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                example = json.loads(first_line)
                print(json.dumps(example, ensure_ascii=False, indent=2))
        
        return True
        
    except Exception as e:
        print(f"❌ 错误：处理文件时发生异常: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: python convert_to_messages_format.py <input_file> [output_file]")
        print("\n示例:")
        print("  python convert_to_messages_format.py train.jsonl")
        print("  python convert_to_messages_format.py train.jsonl train_messages.jsonl")
        print("\n说明:")
        print("  将 prompt/response 格式转换为 dashscope 需要的 messages 格式（ChatML）")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = convert_file(input_file, output_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

