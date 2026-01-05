#!/bin/bash
# 增量生成进度监控脚本

echo "=========================================="
echo "  批量数据生成进度监控"
echo "=========================================="
echo ""

# 检查进程状态
PID=$(ps aux | grep "main.py batch-generate" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "❌ 任务已停止或未运行"
    echo ""
    echo "查看完整日志:"
    echo "  cat batch_generate.log"
    exit 1
else
    echo "✅ 任务正在运行 (PID: $PID)"
    
    # 获取CPU和内存使用
    ps -p $PID -o %cpu,%mem,etime,command | tail -n 1
    echo ""
fi

# 日志统计
echo "📊 日志统计:"
echo "  总行数: $(wc -l < batch_generate.log)"
echo ""

# 最新进度
echo "📝 最新进度 (最后30行):"
echo "---"
tail -n 30 batch_generate.log
echo "---"
echo ""

# 数据统计
if [ -d "output/complete_training" ]; then
    echo "💾 输出文件:"
    ls -lh output/complete_training/ 2>/dev/null | tail -n +2
    echo ""
fi

# 仓库进度统计
echo "🔍 处理进度:"
QA_COUNT=$(grep -c "生成.*QA" batch_generate.log 2>/dev/null || echo "0")
DESIGN_COUNT=$(grep -c "生成.*设计方案" batch_generate.log 2>/dev/null || echo "0")
ERROR_COUNT=$(grep -c "失败\|错误\|Error\|Failed" batch_generate.log 2>/dev/null || echo "0")

echo "  已生成QA数据的仓库: $QA_COUNT"
echo "  已生成Design数据的仓库: $DESIGN_COUNT"
echo "  错误/失败数: $ERROR_COUNT"
echo ""

echo "=========================================="
echo "实时监控命令:"
echo "  watch -n 5 './scripts/monitoring/monitor_progress.sh'  # 每5秒刷新"
echo "  tail -f batch_generate.log                              # 实时日志"
echo "=========================================="

