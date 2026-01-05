# 安装部署指南

本文档详细介绍如何安装和配置智能训练数据生成系统。

## 环境要求

### 系统要求

- **操作系统**: macOS、Linux 或 Windows 10/11
- **Python**: 3.10 或更高版本
- **内存**: 建议 8GB 以上
- **磁盘空间**: 至少 10GB（用于下载的代码仓库和生成的数据）

### 可选依赖

- **GPU**: 本地 LoRA 微调需要 NVIDIA GPU（16GB+ 显存）
- **Git**: 用于 GitHub 自动发现功能

## 安装步骤

### 1. 克隆项目

```bash
git clone <repo-url>
cd IntelligentTrainingDataSystem
```

### 2. 创建虚拟环境（推荐）

**macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

激活后，命令提示符会显示 `(venv)`：

```bash
(venv) user@machine IntelligentTrainingDataSystem %
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 可选依赖

```bash
# DashScope 微调相关
pip install dashscope pyyaml

# 本地 GPU 微调相关（需要 CUDA）
pip install torch transformers peft datasets accelerate
```

### 4. 验证安装

运行以下命令验证安装是否成功：

```bash
python -c "from src.generators import QAGenerator; print('✅ 安装成功')"
```

或运行演示脚本：

```bash
python examples/demo.py
```

## 配置说明

### API 密钥配置

1. 复制配置示例文件：

```bash
cp config.example.env .env
```

2. 编辑 `.env` 文件，填入你的 API 密钥：

```bash
# LLM API 配置（必需）
LLM_PROVIDER=qwen
LLM_API_KEY=your_dashscope_api_key_here
LLM_MODEL_NAME=qwen-plus

# GitHub Token（可选，用于提高 API 限额）
GITHUB_TOKEN=your_github_token_here
```

### 获取 API 密钥

- **DashScope API Key**: 访问 [DashScope 控制台](https://dashscope.console.aliyun.com/) 获取
- **GitHub Token**: 访问 [GitHub Settings > Tokens](https://github.com/settings/tokens) 创建

详细配置说明请参考 [配置说明](configuration.md)。

## 虚拟环境详解

### 为什么使用虚拟环境？

- **隔离性**: 项目依赖相互隔离，避免版本冲突
- **可重复性**: 确保开发、测试、生产环境一致
- **便于管理**: 易于卸载和重建环境

### 常用命令

| 操作 | 命令 |
|------|------|
| 激活环境 | `source venv/bin/activate` (Linux/Mac) 或 `venv\Scripts\activate` (Windows) |
| 退出环境 | `deactivate` |
| 查看已安装包 | `pip list` |
| 导出依赖 | `pip freeze > requirements.txt` |
| 删除环境 | `rm -rf venv` |

### IDE 配置

**VS Code:**

1. 打开命令面板（Cmd+Shift+P）
2. 选择 "Python: Select Interpreter"
3. 选择 `./venv/bin/python`

**PyCharm:**

1. Settings → Project → Python Interpreter
2. 添加 Local Interpreter
3. 选择 `./venv/bin/python`

## 验证环境

运行此脚本验证环境配置：

```bash
python3 << 'EOF'
import sys
import os

print("=" * 60)
print("Python 环境信息")
print("=" * 60)

print(f"Python 版本: {sys.version}")
print(f"Python 路径: {sys.executable}")
print(f"虚拟环境: {'是' if hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix else '否'}")
print()

print("已安装的包:")
try:
    import dashscope
    print("  ✅ dashscope")
except ImportError:
    print("  ❌ dashscope (未安装)")

try:
    import yaml
    print("  ✅ yaml (PyYAML)")
except ImportError:
    print("  ❌ yaml (未安装)")

try:
    from src.generators import QAGenerator
    print("  ✅ IntelligentTrainingDataSystem 模块")
except ImportError:
    print("  ❌ IntelligentTrainingDataSystem 模块")

print()
print("环境变量:")
print(f"  DASHSCOPE_API_KEY: {'已设置' if os.getenv('DASHSCOPE_API_KEY') else '未设置'}")
print(f"  LLM_API_KEY: {'已设置' if os.getenv('LLM_API_KEY') else '未设置'}")
print()

print("=" * 60)
print("环境检查完成")
print("=" * 60)
EOF
```

## 常见问题

### Q: 提示 "dashscope SDK 未安装"

**A:** 确保在虚拟环境中安装：

```bash
source venv/bin/activate
pip install dashscope
```

### Q: 主脚本和子脚本使用不同的 Python 环境

**A:** 系统已修复此问题。所有脚本都使用 `sys.executable` 确保环境一致。

### Q: Windows 上无法激活虚拟环境

**A:** 可能需要修改执行策略：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

更多问题请参考 [问题排查](../troubleshooting/common-issues.md)。

## 下一步

- [快速开始](quick-start.md) - 5分钟上手教程

