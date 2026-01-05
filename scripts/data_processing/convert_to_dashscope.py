#!/usr/bin/env python3
"""
数据格式转换脚本 - 将 Alpaca/JSONL 格式转换为 DashScope 微调格式
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import sys


def load_alpaca_data(file_path: Path) -> List[Dict[str, Any]]:
    """加载 Alpaca 格式数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def convert_to_prompt_response(item: Dict[str, Any]) -> Dict[str, str]:
    """
    转换为 DashScope 的 prompt-response 格式
    
    输入格式（Alpaca）:
    {
        "instruction": "问题",
        "input": "上下文",
        "output": "答案"
    }
    
    输出格式（DashScope）:
    {
        "prompt": "问题 + 上下文",
        "response": "答案"
    }
    """
    # 构建 prompt
    prompt = item.get('instruction', '')
    input_text = item.get('input', '')
    
    if input_text:
        prompt = f"{prompt}\n\n{input_text}"
    
    # 构建 response
    response = item.get('output', '')
    
    return {
        "prompt": prompt.strip(),
        "response": response.strip()
    }


def convert_to_messages(item: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """
    转换为 DashScope 的 messages 格式
    
    输出格式（DashScope）:
    {
        "messages": [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "用户问题"},
            {"role": "assistant", "content": "助手回答"}
        ]
    }
    """
    messages = []
    
    # 添加系统提示（可选）
    messages.append({
        "role": "system",
        "content": "你是一个专业的代码分析和设计助手，能够理解代码逻辑并提供详细的解释和建议。"
    })
    
    # 添加用户消息
    prompt = item.get('instruction', '')
    input_text = item.get('input', '')
    
    user_content = prompt
    if input_text:
        user_content = f"{prompt}\n\n{input_text}"
    
    messages.append({
        "role": "user",
        "content": user_content.strip()
    })
    
    # 添加助手回答
    messages.append({
        "role": "assistant",
        "content": item.get('output', '').strip()
    })
    
    return {"messages": messages}


def validate_data(data: List[Dict[str, Any]], format_type: str) -> tuple:
    """验证数据格式和质量"""
    valid_count = 0
    invalid_count = 0
    warnings = []
    
    for i, item in enumerate(data):
        is_valid = True
        
        if format_type == 'prompt-response':
            if not item.get('prompt') or not item.get('response'):
                is_valid = False
                warnings.append(f"第 {i+1} 条：prompt 或 response 为空")
            elif len(item['prompt']) < 10:
                warnings.append(f"第 {i+1} 条：prompt 过短（< 10 字符）")
            elif len(item['response']) < 20:
                warnings.append(f"第 {i+1} 条：response 过短（< 20 字符）")
        
        elif format_type == 'messages':
            messages = item.get('messages', [])
            if len(messages) < 2:
                is_valid = False
                warnings.append(f"第 {i+1} 条：消息数量不足")
        
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
    
    return valid_count, invalid_count, warnings


def main():
    parser = argparse.ArgumentParser(
        description='将训练数据转换为 DashScope 微调格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换为 prompt-response 格式（推荐）
  python convert_to_dashscope.py train.alpaca -o train.jsonl --format prompt-response
  
  # 转换为 messages 格式
  python convert_to_dashscope.py train.alpaca -o train.jsonl --format messages
  
  # 验证但不转换
  python convert_to_dashscope.py train.alpaca --validate-only
        """
    )
    
    parser.add_argument(
        'input_file',
        type=str,
        help='输入文件路径（Alpaca 或 JSONL 格式）'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='输出文件路径（JSONL 格式）'
    )
    
    parser.add_argument(
        '--format',
        choices=['prompt-response', 'messages'],
        default='prompt-response',
        help='输出格式类型（默认: prompt-response）'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='仅验证数据，不执行转换'
    )
    
    parser.add_argument(
        '--max-samples',
        type=int,
        help='最大转换数量（用于测试）'
    )
    
    args = parser.parse_args()
    
    # 检查输入文件
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ 错误: 输入文件不存在: {input_path}")
        sys.exit(1)
    
    print(f"📖 加载数据: {input_path}")
    
    try:
        data = load_alpaca_data(input_path)
        print(f"✅ 成功加载 {len(data)} 条数据")
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        sys.exit(1)
    
    # 限制样本数量
    if args.max_samples and args.max_samples < len(data):
        data = data[:args.max_samples]
        print(f"📝 限制为前 {args.max_samples} 条数据")
    
    # 转换数据
    print(f"🔄 转换为 {args.format} 格式...")
    
    converted_data = []
    for item in data:
        try:
            if args.format == 'prompt-response':
                converted_item = convert_to_prompt_response(item)
            else:  # messages
                converted_item = convert_to_messages(item)
            
            converted_data.append(converted_item)
        except Exception as e:
            print(f"⚠️  警告: 转换失败: {e}")
            continue
    
    print(f"✅ 成功转换 {len(converted_data)} 条数据")
    
    # 验证数据
    print("🔍 验证数据质量...")
    valid_count, invalid_count, warnings = validate_data(converted_data, args.format)
    
    print(f"✅ 有效数据: {valid_count}")
    if invalid_count > 0:
        print(f"⚠️  无效数据: {invalid_count}")
    
    if warnings and len(warnings) <= 10:
        print("\n⚠️  数据质量警告:")
        for warning in warnings:
            print(f"  - {warning}")
    elif len(warnings) > 10:
        print(f"\n⚠️  共有 {len(warnings)} 个数据质量警告（仅显示前 10 个）:")
        for warning in warnings[:10]:
            print(f"  - {warning}")
    
    # 如果仅验证，则退出
    if args.validate_only:
        print("\n✅ 验证完成（未执行转换）")
        return
    
    # 检查输出文件
    if not args.output:
        print("❌ 错误: 需要指定输出文件 (-o)")
        sys.exit(1)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存数据
    print(f"\n💾 保存数据: {output_path}")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in converted_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        print(f"✅ 成功保存 {len(converted_data)} 条数据")
        
        # 显示示例
        print("\n📝 数据示例（前 2 条）:")
        for i, item in enumerate(converted_data[:2]):
            print(f"\n--- 示例 {i+1} ---")
            print(json.dumps(item, ensure_ascii=False, indent=2))
        
        # 显示统计信息
        file_size = output_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"\n📊 统计信息:")
        print(f"  - 文件大小: {file_size_mb:.2f} MB")
        print(f"  - 数据条数: {len(converted_data)}")
        print(f"  - 平均大小: {file_size / len(converted_data):.0f} bytes/条")
        
        print("\n✅ 转换完成!")
        print(f"\n下一步:")
        print(f"  1. 验证数据: python scripts/validate_dashscope_data.py {output_path}")
        print(f"  2. 开始微调: python scripts/dashscope_finetune.py <config_file>")
        
    except Exception as e:
        print(f"❌ 保存数据失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

