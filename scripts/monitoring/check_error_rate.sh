#!/bin/bash
echo "=== 错误率统计 ==="
echo ""

# 查找日志文件
if [ -f "batch_generate.log" ]; then
    LOG_FILE="batch_generate.log"
else
    LOG_FILE=$(ls -t output/*/batch_*.log 2>/dev/null | head -n 1)
fi

if [ -z "$LOG_FILE" ]; then
    echo "❌ 找不到日志文件"
    exit 1
fi

echo "日志文件: $LOG_FILE"
echo ""

# 统计
TOTAL_ATTEMPTS=$(grep -c "生成.*QA\|处理.*文件" "$LOG_FILE" 2>/dev/null || echo "0")
JSON_ERRORS=$(grep -c "无法解析 JSON\|JSON 解析.*失败" "$LOG_FILE" 2>/dev/null || echo "0")
SUCCESS_QA=$(grep -c "✓.*生成.*QA" "$LOG_FILE" 2>/dev/null || echo "0")
SUCCESS_DESIGN=$(grep -c "✓.*生成.*设计" "$LOG_FILE" 2>/dev/null || echo "0")
TOTAL_ERRORS=$(grep -c "失败\|错误\|Error\|Failed" "$LOG_FILE" 2>/dev/null || echo "0")

echo "📊 统计数据:"
echo "  成功生成 QA: $SUCCESS_QA 个仓库"
echo "  成功生成 Design: $SUCCESS_DESIGN 个仓库"
echo "  JSON 解析错误: $JSON_ERRORS 次"
echo "  总错误/警告: $TOTAL_ERRORS 次"
echo ""

if [ $SUCCESS_QA -gt 0 ]; then
    if [ $JSON_ERRORS -eq 0 ]; then
        ERROR_RATE=0
    else
        ERROR_RATE=$((JSON_ERRORS * 100 / SUCCESS_QA))
    fi
    
    echo "📈 错误率评估:"
    echo "  JSON 解析错误率: ~$ERROR_RATE%"
    echo ""
    
    if [ $ERROR_RATE -lt 5 ]; then
        echo "✅ 状态: 优秀（错误率很低）"
    elif [ $ERROR_RATE -lt 15 ]; then
        echo "🟡 状态: 正常（错误率可接受）"
    else
        echo "🔴 状态: 需要关注（错误率偏高）"
    fi
else
    echo "⏳ 任务刚开始，等待更多数据..."
fi

echo ""
echo "=== 最近的错误 (最后5条) ==="
grep "无法解析 JSON\|JSON 解析.*失败" "$LOG_FILE" 2>/dev/null | tail -n 5 || echo "无"

