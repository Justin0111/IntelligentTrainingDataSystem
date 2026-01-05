#!/usr/bin/env python3
"""
DashScope 数据验证脚本 - 验证数据格式是否符合 DashScope 要求
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
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
                    print(f"⚠️  第 {line_num} 行 JSON 解析错误: {e}")
    return data


def detect_format(data: List[Dict[str, Any]]) -> str:
    """检测数据格式"""
    if not data:
        return "unknown"
    
    first_item = data[0]
    
    if "prompt" in first_item and "response" in first_item:
        return "prompt-response"
    elif "messages" in first_item:
        return "messages"
    else:
        return "unknown"


def validate_prompt_response_format(data: List[Dict[str, Any]]) -> Dict:
    """验证 prompt-response 格式"""
    results = {
        "valid": 0,
        "invalid": 0,
        "warnings": [],
        "errors": [],
        "stats": {
            "avg_prompt_length": 0,
            "avg_response_length": 0,
            "min_prompt_length": float('inf'),
            "max_prompt_length": 0,
            "min_response_length": float('inf'),
            "max_response_length": 0,
        }
    }
    
    total_prompt_len = 0
    total_response_len = 0
    
    for i, item in enumerate(data, 1):
        is_valid = True
        
        # 检查必需字段
        if "prompt" not in item:
            results["errors"].append(f"第 {i} 条: 缺少 'prompt' 字段")
            is_valid = False
        
        if "response" not in item:
            results["errors"].append(f"第 {i} 条: 缺少 'response' 字段")
            is_valid = False
        
        if not is_valid:
            results["invalid"] += 1
            continue
        
        prompt = item["prompt"]
        response = item["response"]
        
        # 检查类型
        if not isinstance(prompt, str):
            results["errors"].append(f"第 {i} 条: 'prompt' 不是字符串类型")
            is_valid = False
        
        if not isinstance(response, str):
            results["errors"].append(f"第 {i} 条: 'response' 不是字符串类型")
            is_valid = False
        
        if not is_valid:
            results["invalid"] += 1
            continue
        
        # 检查长度
        prompt_len = len(prompt)
        response_len = len(response)
        
        if prompt_len < 5:
            results["warnings"].append(f"第 {i} 条: prompt 过短 ({prompt_len} 字符)")
        
        if response_len < 10:
            results["warnings"].append(f"第 {i} 条: response 过短 ({response_len} 字符)")
        
        if prompt_len > 4000:
            results["warnings"].append(f"第 {i} 条: prompt 过长 ({prompt_len} 字符)，可能超出模型限制")
        
        if response_len > 2000:
            results["warnings"].append(f"第 {i} 条: response 过长 ({response_len} 字符)")
        
        # 检查空白
        if not prompt.strip():
            results["errors"].append(f"第 {i} 条: prompt 为空或仅包含空白字符")
            is_valid = False
        
        if not response.strip():
            results["errors"].append(f"第 {i} 条: response 为空或仅包含空白字符")
            is_valid = False
        
        if is_valid:
            results["valid"] += 1
            total_prompt_len += prompt_len
            total_response_len += response_len
            
            # 更新统计
            results["stats"]["min_prompt_length"] = min(results["stats"]["min_prompt_length"], prompt_len)
            results["stats"]["max_prompt_length"] = max(results["stats"]["max_prompt_length"], prompt_len)
            results["stats"]["min_response_length"] = min(results["stats"]["min_response_length"], response_len)
            results["stats"]["max_response_length"] = max(results["stats"]["max_response_length"], response_len)
        else:
            results["invalid"] += 1
    
    # 计算平均值
    if results["valid"] > 0:
        results["stats"]["avg_prompt_length"] = total_prompt_len / results["valid"]
        results["stats"]["avg_response_length"] = total_response_len / results["valid"]
    
    return results


def validate_messages_format(data: List[Dict[str, Any]]) -> Dict:
    """验证 messages 格式"""
    results = {
        "valid": 0,
        "invalid": 0,
        "warnings": [],
        "errors": [],
        "stats": {
            "avg_messages": 0,
            "role_distribution": {}
        }
    }
    
    total_messages = 0
    
    for i, item in enumerate(data, 1):
        is_valid = True
        
        # 检查必需字段
        if "messages" not in item:
            results["errors"].append(f"第 {i} 条: 缺少 'messages' 字段")
            results["invalid"] += 1
            continue
        
        messages = item["messages"]
        
        # 检查类型
        if not isinstance(messages, list):
            results["errors"].append(f"第 {i} 条: 'messages' 不是数组类型")
            results["invalid"] += 1
            continue
        
        # 检查消息数量
        if len(messages) < 2:
            results["errors"].append(f"第 {i} 条: 至少需要 2 条消息（user + assistant）")
            is_valid = False
        
        # 检查每条消息
        has_user = False
        has_assistant = False
        
        for j, msg in enumerate(messages):
            if not isinstance(msg, dict):
                results["errors"].append(f"第 {i} 条，消息 {j+1}: 消息不是对象类型")
                is_valid = False
                continue
            
            # 检查必需字段
            if "role" not in msg:
                results["errors"].append(f"第 {i} 条，消息 {j+1}: 缺少 'role' 字段")
                is_valid = False
            
            if "content" not in msg:
                results["errors"].append(f"第 {i} 条，消息 {j+1}: 缺少 'content' 字段")
                is_valid = False
            
            if "role" in msg and "content" in msg:
                role = msg["role"]
                content = msg["content"]
                
                # 检查角色
                if role not in ["system", "user", "assistant"]:
                    results["warnings"].append(f"第 {i} 条，消息 {j+1}: 未知角色 '{role}'")
                
                # 统计角色
                results["stats"]["role_distribution"][role] = results["stats"]["role_distribution"].get(role, 0) + 1
                
                if role == "user":
                    has_user = True
                elif role == "assistant":
                    has_assistant = True
                
                # 检查内容
                if not isinstance(content, str) or not content.strip():
                    results["errors"].append(f"第 {i} 条，消息 {j+1}: content 为空或无效")
                    is_valid = False
        
        # 检查是否有 user 和 assistant
        if not has_user:
            results["warnings"].append(f"第 {i} 条: 缺少 'user' 角色的消息")
        
        if not has_assistant:
            results["warnings"].append(f"第 {i} 条: 缺少 'assistant' 角色的消息")
        
        if is_valid:
            results["valid"] += 1
            total_messages += len(messages)
        else:
            results["invalid"] += 1
    
    # 计算平均值
    if results["valid"] > 0:
        results["stats"]["avg_messages"] = total_messages / results["valid"]
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='验证 DashScope 微调数据格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python validate_dashscope_data.py train.jsonl
  python validate_dashscope_data.py train.jsonl --max-warnings 20
        """
    )
    
    parser.add_argument(
        'input_file',
        type=str,
        help='输入文件路径（JSONL 格式）'
    )
    
    parser.add_argument(
        '--max-warnings',
        type=int,
        default=10,
        help='显示的最大警告数量（默认: 10）'
    )
    
    parser.add_argument(
        '--max-errors',
        type=int,
        default=10,
        help='显示的最大错误数量（默认: 10）'
    )
    
    args = parser.parse_args()
    
    # 检查输入文件
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ 错误: 文件不存在: {input_path}")
        sys.exit(1)
    
    print(f"📖 加载数据: {input_path}")
    
    try:
        data = load_jsonl(input_path)
        print(f"✅ 成功加载 {len(data)} 条数据")
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        sys.exit(1)
    
    if not data:
        print("❌ 错误: 文件为空")
        sys.exit(1)
    
    # 检测格式
    format_type = detect_format(data)
    print(f"🔍 检测到格式: {format_type}")
    
    if format_type == "unknown":
        print("❌ 错误: 无法识别的数据格式")
        print("支持的格式:")
        print("  1. prompt-response: {\"prompt\": \"...\", \"response\": \"...\"}")
        print("  2. messages: {\"messages\": [{\"role\": \"...\", \"content\": \"...\"}]}")
        sys.exit(1)
    
    # 验证数据
    print(f"\n🔍 验证数据...")
    
    if format_type == "prompt-response":
        results = validate_prompt_response_format(data)
    else:  # messages
        results = validate_messages_format(data)
    
    # 显示结果
    print(f"\n{'='*60}")
    print("📊 验证结果")
    print(f"{'='*60}")
    
    total = results["valid"] + results["invalid"]
    valid_percent = (results["valid"] / total * 100) if total > 0 else 0
    
    print(f"\n✅ 有效数据: {results['valid']} / {total} ({valid_percent:.1f}%)")
    
    if results["invalid"] > 0:
        print(f"❌ 无效数据: {results['invalid']}")
    
    # 显示错误
    if results["errors"]:
        print(f"\n❌ 错误 (共 {len(results['errors'])} 个，显示前 {args.max_errors} 个):")
        for error in results["errors"][:args.max_errors]:
            print(f"  - {error}")
        
        if len(results["errors"]) > args.max_errors:
            print(f"  ... 还有 {len(results['errors']) - args.max_errors} 个错误")
    
    # 显示警告
    if results["warnings"]:
        print(f"\n⚠️  警告 (共 {len(results['warnings'])} 个，显示前 {args.max_warnings} 个):")
        for warning in results["warnings"][:args.max_warnings]:
            print(f"  - {warning}")
        
        if len(results["warnings"]) > args.max_warnings:
            print(f"  ... 还有 {len(results['warnings']) - args.max_warnings} 个警告")
    
    # 显示统计信息
    if results["valid"] > 0:
        print(f"\n📊 统计信息:")
        
        if format_type == "prompt-response":
            stats = results["stats"]
            print(f"  Prompt 长度:")
            print(f"    - 平均: {stats['avg_prompt_length']:.0f} 字符")
            print(f"    - 范围: {stats['min_prompt_length']} - {stats['max_prompt_length']} 字符")
            print(f"  Response 长度:")
            print(f"    - 平均: {stats['avg_response_length']:.0f} 字符")
            print(f"    - 范围: {stats['min_response_length']} - {stats['max_response_length']} 字符")
        
        elif format_type == "messages":
            stats = results["stats"]
            print(f"  平均消息数: {stats['avg_messages']:.1f}")
            print(f"  角色分布:")
            for role, count in sorted(stats['role_distribution'].items()):
                print(f"    - {role}: {count}")
    
    # 总结
    print(f"\n{'='*60}")
    
    if results["invalid"] == 0 and not results["errors"]:
        print("✅ 数据格式完全符合 DashScope 要求！")
        print("\n下一步:")
        print("  开始微调: python scripts/dashscope_finetune.py <config_file>")
        sys.exit(0)
    else:
        print("❌ 数据存在问题，请修复后再继续")
        sys.exit(1)


if __name__ == '__main__':
    main()

