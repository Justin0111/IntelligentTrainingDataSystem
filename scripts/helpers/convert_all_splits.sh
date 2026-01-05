#!/bin/bash
# 批量转换所有数据集划分（train/valid/test）

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}批量转换数据集为 DashScope 格式${NC}"
echo ""

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <数据集基础路径> [输出目录]"
    echo ""
    echo "示例:"
    echo "  $0 output/merged/merged_all_20260105"
    echo "  $0 output/merged/merged_all_20260105 output/dashscope"
    echo ""
    echo "说明:"
    echo "  - 数据集基础路径：不含 _train/_valid/_test 后缀"
    echo "  - 输出目录：可选，默认为 output/dashscope"
    exit 1
fi

BASE_PATH=$1
OUTPUT_DIR=${2:-output/dashscope}

echo -e "${BLUE}输入基础路径: ${NC}$BASE_PATH"
echo -e "${BLUE}输出目录: ${NC}$OUTPUT_DIR"
echo ""

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 转换训练集
TRAIN_FILE="${BASE_PATH}_train.alpaca"
if [ -f "$TRAIN_FILE" ]; then
    echo -e "${GREEN}✓${NC} 转换训练集: $TRAIN_FILE"
    python3 scripts/convert_to_dashscope.py \
        "$TRAIN_FILE" \
        -o "$OUTPUT_DIR/train.jsonl" \
        --format prompt-response
    echo ""
else
    echo -e "${YELLOW}⚠${NC}  未找到训练集: $TRAIN_FILE"
fi

# 转换验证集
VALID_FILE="${BASE_PATH}_valid.alpaca"
if [ -f "$VALID_FILE" ]; then
    echo -e "${GREEN}✓${NC} 转换验证集: $VALID_FILE"
    python3 scripts/convert_to_dashscope.py \
        "$VALID_FILE" \
        -o "$OUTPUT_DIR/valid.jsonl" \
        --format prompt-response
    echo ""
else
    echo -e "${YELLOW}⚠${NC}  未找到验证集: $VALID_FILE"
fi

# 转换测试集
TEST_FILE="${BASE_PATH}_test.alpaca"
if [ -f "$TEST_FILE" ]; then
    echo -e "${GREEN}✓${NC} 转换测试集: $TEST_FILE"
    python3 scripts/convert_to_dashscope.py \
        "$TEST_FILE" \
        -o "$OUTPUT_DIR/test.jsonl" \
        --format prompt-response
    echo ""
else
    echo -e "${YELLOW}⚠${NC}  未找到测试集: $TEST_FILE"
fi

echo -e "${GREEN}✓${NC} 转换完成！"
echo ""
echo "输出文件："
ls -lh "$OUTPUT_DIR"/*.jsonl 2>/dev/null || echo "  (无文件)"

