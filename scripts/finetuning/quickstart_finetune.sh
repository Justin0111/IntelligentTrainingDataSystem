#!/bin/bash
# DashScope 微调快速开始脚本

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}${'='*60}${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}${'='*60}${NC}"
    echo ""
}

# 检查依赖
check_dependencies() {
    print_header "检查依赖"
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        print_error "未找到 Python 3"
        exit 1
    fi
    print_success "Python 3: $(python3 --version)"
    
    # 检查 dashscope SDK
    if ! python3 -c "import dashscope" 2>/dev/null; then
        print_warning "未安装 dashscope SDK"
        print_info "正在安装..."
        pip install dashscope
    fi
    print_success "dashscope SDK 已安装"
    
    # 检查 PyYAML
    if ! python3 -c "import yaml" 2>/dev/null; then
        print_warning "未安装 PyYAML"
        print_info "正在安装..."
        pip install pyyaml
    fi
    print_success "PyYAML 已安装"
}

# 检查 API Key
check_api_key() {
    print_header "检查 API Key"
    
    if [ -z "$DASHSCOPE_API_KEY" ]; then
        print_error "未设置 DASHSCOPE_API_KEY 环境变量"
        echo ""
        echo "请设置环境变量:"
        echo "  export DASHSCOPE_API_KEY='your-api-key'"
        echo ""
        echo "或在配置文件中设置 api_key"
        exit 1
    fi
    
    print_success "API Key 已设置"
}

# 查找训练数据
find_training_data() {
    print_header "查找训练数据"
    
    # 查找最新的训练数据
    TRAIN_FILE=$(ls -t output/complete_training/merged_qa_dataset_*_train.alpaca 2>/dev/null | head -1)
    VALID_FILE=$(ls -t output/complete_training/merged_qa_dataset_*_valid.alpaca 2>/dev/null | head -1)
    TEST_FILE=$(ls -t output/complete_training/merged_qa_dataset_*_test.alpaca 2>/dev/null | head -1)
    
    if [ -z "$TRAIN_FILE" ]; then
        print_error "未找到训练数据文件"
        echo ""
        echo "请先生成训练数据:"
        echo "  python main.py batch-generate <repos_file> -o output/complete_training --split"
        exit 1
    fi
    
    print_success "训练数据: $TRAIN_FILE"
    
    if [ -n "$VALID_FILE" ]; then
        print_success "验证数据: $VALID_FILE"
    else
        print_warning "未找到验证数据文件"
    fi
    
    if [ -n "$TEST_FILE" ]; then
        print_success "测试数据: $TEST_FILE"
    fi
}

# 转换数据格式
convert_data() {
    print_header "转换数据格式"
    
    mkdir -p output/dashscope
    
    # 转换训练集
    print_info "转换训练集..."
    python3 scripts/convert_to_dashscope.py \
        "$TRAIN_FILE" \
        -o output/dashscope/train.jsonl \
        --format prompt-response
    
    # 转换验证集
    if [ -n "$VALID_FILE" ]; then
        print_info "转换验证集..."
        python3 scripts/convert_to_dashscope.py \
            "$VALID_FILE" \
            -o output/dashscope/valid.jsonl \
            --format prompt-response
    fi
    
    # 转换测试集
    if [ -n "$TEST_FILE" ]; then
        print_info "转换测试集..."
        python3 scripts/convert_to_dashscope.py \
            "$TEST_FILE" \
            -o output/dashscope/test.jsonl \
            --format prompt-response
    fi
    
    print_success "数据格式转换完成"
}

# 验证数据
validate_data() {
    print_header "验证数据格式"
    
    print_info "验证训练数据..."
    python3 scripts/validate_dashscope_data.py output/dashscope/train.jsonl
    
    if [ $? -ne 0 ]; then
        print_error "数据验证失败"
        exit 1
    fi
    
    print_success "数据验证通过"
}

# 创建配置文件
create_config() {
    print_header "创建配置文件"
    
    CONFIG_FILE="scripts/finetune_config.yaml"
    
    if [ -f "$CONFIG_FILE" ]; then
        print_warning "配置文件已存在: $CONFIG_FILE"
        read -p "是否覆盖? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "使用现有配置文件"
            return
        fi
    fi
    
    # 创建配置文件
    cat > "$CONFIG_FILE" << EOF
# DashScope 微调配置文件
api_key: "$DASHSCOPE_API_KEY"

base_model: "qwen-turbo"
model_name: "qwen-turbo-code-$(date +%Y%m%d)"

train_file: "output/dashscope/train.jsonl"
valid_file: "output/dashscope/valid.jsonl"

hyperparameters:
  epochs: 3
  batch_size: 16
  learning_rate: 2e-5
EOF
    
    print_success "配置文件已创建: $CONFIG_FILE"
}

# 开始微调
start_finetune() {
    print_header "开始微调"
    
    print_info "使用配置: scripts/finetune_config.yaml"
    
    # 注意：这里需要根据实际的 DashScope API 调整
    # 当前脚本假设使用 SDK 方式
    print_warning "即将开始微调，这将产生费用"
    read -p "是否继续? (y/N) " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "已取消"
        exit 0
    fi
    
    python3 scripts/dashscope_finetune.py scripts/finetune_config.yaml
}

# 显示帮助信息
show_help() {
    echo "DashScope 微调快速开始脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help              显示此帮助信息"
    echo "  --skip-convert      跳过数据转换步骤"
    echo "  --skip-validate     跳过数据验证步骤"
    echo "  --config FILE       使用指定的配置文件"
    echo ""
    echo "环境变量:"
    echo "  DASHSCOPE_API_KEY   DashScope API Key（必需）"
    echo ""
    echo "示例:"
    echo "  # 完整流程"
    echo "  export DASHSCOPE_API_KEY='your-api-key'"
    echo "  $0"
    echo ""
    echo "  # 跳过转换和验证（数据已准备好）"
    echo "  $0 --skip-convert --skip-validate"
}

# 主函数
main() {
    # 解析参数
    SKIP_CONVERT=false
    SKIP_VALIDATE=false
    CONFIG_FILE=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                show_help
                exit 0
                ;;
            --skip-convert)
                SKIP_CONVERT=true
                shift
                ;;
            --skip-validate)
                SKIP_VALIDATE=true
                shift
                ;;
            --config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_header "DashScope 微调快速开始"
    
    # 1. 检查依赖
    check_dependencies
    
    # 2. 检查 API Key
    check_api_key
    
    # 3. 查找训练数据
    if [ "$SKIP_CONVERT" = false ]; then
        find_training_data
        
        # 4. 转换数据格式
        convert_data
    fi
    
    # 5. 验证数据
    if [ "$SKIP_VALIDATE" = false ]; then
        validate_data
    fi
    
    # 6. 创建配置文件
    if [ -z "$CONFIG_FILE" ]; then
        create_config
    else
        print_info "使用配置文件: $CONFIG_FILE"
    fi
    
    # 7. 开始微调
    start_finetune
    
    print_header "完成"
    print_success "微调任务已启动"
    echo ""
    echo "下一步:"
    echo "  1. 等待训练完成（约 20-60 分钟）"
    echo "  2. 使用微调后的模型进行推理"
    echo "  3. 评估模型效果"
}

# 运行主函数
main "$@"

