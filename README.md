# 智能训练数据生成与处理系统

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

基于本地代码仓库的智能训练数据生成系统，为 Qwen 2.5 系列模型微调提供高质量的训练数据集。

## 核心功能

- **问答对生成** - 自动分析代码仓库，生成高质量的代码相关问答对
- **设计方案生成** - 基于现有架构为新需求生成设计方案
- **GitHub 自动发现** - 根据业务场景自动搜索下载优质仓库
- **批量处理** - 支持多仓库批量生成和数据平衡
- **DashScope 微调** - 一键完成数据转换和模型微调

## 支持的业务场景

系统支持多种业务场景的代码仓库自动发现和数据生成，确保训练数据的丰富性和多样性：

| 场景 | 覆盖领域 |
|------|---------|
| **金融科技** | 支付系统、交易平台、区块链、钱包服务 |
| **电商系统** | 电商平台、购物车、订单系统、商品管理 |
| **微服务架构** | 微服务、API网关、服务网格、容器化 |
| **数据处理** | ETL、数据管道、数据分析、数据仓库 |
| **Web框架** | Web框架、REST API、GraphQL、后端服务 |
| **机器学习** | 机器学习、深度学习、神经网络 |
| **DevOps工具** | CI/CD、监控、日志、自动化部署 |
| **认证授权** | 用户认证、OAuth、JWT、权限管理 |
| **消息队列** | 消息队列、事件驱动、发布订阅 |
| **API服务** | API服务器、HTTP服务、RESTful接口 |

通过 GitHub 自动发现功能，系统可以根据这些场景自动搜索、下载并处理相关的高质量开源仓库，生成覆盖多领域的训练数据集。

## 快速开始

### 安装

```bash
git clone <repo-url>
cd IntelligentTrainingDataSystem
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件并配置 API 密钥：

```bash
LLM_API_KEY=your_dashscope_api_key_here
```

### 使用

```bash
# 分析代码仓库
python main.py analyze /path/to/repo

# 生成问答对数据
python main.py generate-qa /path/to/repo -o output/datasets

# 批量处理多个仓库
python main.py batch-generate repos.txt -o output/batch --split

# 自动发现 GitHub 仓库并生成数据
python main.py auto-discover -s 金融科技 --auto-generate --split
```

## 项目结构

```
IntelligentTrainingDataSystem/
├── main.py                 # CLI 主入口
├── src/                    # 核心源代码
│   ├── parsers/            # 代码解析模块
│   ├── analyzers/          # 代码分析模块
│   ├── generators/         # 数据生成模块
│   ├── processors/         # 数据处理模块
│   └── finetuning/         # 模型微调模块
├── scripts/                # 辅助工具脚本
│   ├── data_processing/    # 数据处理脚本
│   ├── finetuning/         # 微调相关脚本
│   ├── evaluation/         # 评估脚本
│   └── monitoring/         # 监控脚本
├── examples/               # 示例和演示
├── templates/              # Prompt 模板
├── tests/                  # 测试
├── docs/                   # 详细文档
└── output/                 # 输出目录
```

## 文档

完整文档请参阅 [docs/](docs/README.md) 目录：

- [安装部署](docs/getting-started/installation.md)
- [快速开始](docs/getting-started/quick-start.md)
- [批量处理指南](docs/user-guide/batch-processing.md)
- [自动发现功能](docs/user-guide/auto-discovery.md)
- [微调指南](docs/user-guide/finetuning-guide.md)
- [系统架构](docs/architecture/system-design.md)
- [问题排查](docs/troubleshooting/common-issues.md)

## 生成数据示例

系统生成的数据完全满足项目要求，包含完整的代码上下文、推理过程和业务规则。以下是实际生成的数据示例：

### 场景1：问答对数据示例

**要求**：包含原文代码段及推理过程 ✅

```json
{
  "messages": [
    {
      "role": "system",
      "content": "你是一个专业的代码分析和设计助手，能够理解代码逻辑并提供详细的解释和建议。"
    },
    {
      "role": "user",
      "content": "该代码在业务流程中扮演什么角色？\n\n代码上下文：\n```\nexport async function run(projectDir) {\n\tawait fs.rm(projectDir, { recursive: true, force: true });\n```"
    },
    {
      "role": "assistant",
      "content": "推理过程：\n步骤1: 根据提供的业务规则，业务流程为run，表明该函数是流程的一部分。\n步骤2: 代码执行了目录删除操作，符合业务流程中准备环境的需求。\n步骤3: 结合代码功能和业务规则，确定其在流程中的作用是清理旧数据。\n\n该代码在业务流程中负责清理已有的项目目录。这是创建新项目前的必要步骤，确保不会因旧文件而产生冲突或错误。"
    }
  ]
}
```

**数据特点**：
- ✅ 包含完整的代码上下文（代码片段）
- ✅ 提供详细的推理过程（步骤1、步骤2、步骤3）
- ✅ 结合业务规则进行分析
- ✅ 包含元数据（文件路径、函数名等）

### 场景2：设计方案数据示例

**要求**：基于本地代码仓架构的设计方案，包含解释和推理trace ✅

```json
{
  "messages": [
    {
      "role": "system",
      "content": "你是一个专业的架构设计师，能够基于现有代码仓库的架构为新需求设计合理的解决方案。"
    },
    {
      "role": "user",
      "content": "请为以下需求设计一个解决方案：实现购物车功能，支持商品添加、数量调整、优惠券应用和价格计算\n\n现有架构信息：\n- 项目结构：采用分层架构，包含 presentation、api、service、data 等层\n- 现有设计模式：MVC/MVP、分层架构、工厂模式、单例模式\n- 可复用模块：PathwayType、Universe 等核心类，integration_tests 测试模块\n- 依赖关系：支持 Kafka 实时数据处理，包含完整的测试框架"
    },
    {
      "role": "assistant",
      "content": "设计推理过程：\n步骤1: 首先分析现有架构，识别出可复用的模块，如Python核心库和Integration Tests模块，以减少重复开发。\n步骤2: 识别可复用的模块，例如PathwayType和Universe类，用于支持购物车数据模型。\n步骤3: 设计新组件的接口，确保符合MVC/MVP分层架构，提高代码的可维护性和扩展性。\n步骤4: 确定集成策略，确保购物车模块与现有的Kafka和测试模块兼容，以支持实时数据处理和测试需求。\n步骤5: 验证方案可行性，通过模拟测试和代码审查确保购物车功能符合预期。\n\n## 方案概述\n该方案通过引入购物车模块，实现商品添加、数量调整、优惠券应用和价格计算功能。利用现有架构中的模块化设计思想，结合MVC/MVP分层架构和工厂模式，确保代码结构清晰且易于维护。同时，与现有模块如integration_tests和python模块进行集成，以复用现有工具和接口。\n\n## 组件设计\n- **ShoppingCart** (class): 管理购物车的核心逻辑，包括商品的添加、更新、删除以及价格计算。\n- **Item** (class): 表示购物车中的单个商品信息，包含名称、价格、数量等字段。\n- **Coupon** (class): 表示优惠券信息，包括优惠码、折扣类型和折扣金额。\n- **ShoppingCartFactory** (class): 提供创建购物车实例的统一入口，支持不同的购物车配置。"
    }
  ]
}
```

**数据特点**：
- ✅ 基于现有架构分析（识别可复用模块）
- ✅ 提供完整的设计推理过程（5个步骤）
- ✅ 包含组件设计和接口定义
- ✅ 说明集成方案和设计权衡
- ✅ 包含架构上下文信息（项目结构、设计模式、依赖关系）

## 输出格式

支持多种训练数据格式：

- **Alpaca** - 标准指令微调格式
- **ShareGPT** - 对话格式
- **OpenAI** - messages 格式
- **DashScope** - DashScope 微调格式

## 模型微调

### DashScope 在线微调（推荐）

```bash
# 一键完成数据转换和微调
python scripts/finetuning/quickstart_finetune.py
```

### 本地 LoRA 微调（需要 GPU）

```bash
python main.py validate output/datasets/qa_dataset.jsonl --epochs 1
```

## 微调效果对比

以下是使用本系统生成的训练数据基于阿里Dashscope对 Qwen-turbo模型进行微调后的效果对比示例：

---

## 1. 问题 (Session 类的 exists 方法)

```
Session类中的exists方法的作用是什么？

代码上下文：
  exists() {
    return this.username() && this.token();
  }
```

---

## 2. 基础模型（qwen-turbo）响应


在你提供的代码中，`Session` 类中的 `exists()` 方法的作用是 **检查用户是否已经登录或会话是否有效**。

### 详细解释：

#### 1. `exists()` 方法的逻辑：
```js
exists() {
  return this.username() && this.token();
}
```
- 它调用了 `this.username()` 和 `this.token()` 两个方法。
- 只有当这两个方法都返回 **非空值（truthy）** 时，`exists()` 才会返回 `true`，表示用户已登录或会话存在。

#### 2. `username()` 方法：
```js
username() {
  return localStorage.getItem("user");
}
```
- 从浏览器的 `localStorage` 中获取名为 `"user"` 的键对应的值。
- 如果用户已经登录，通常会将用户名或用户信息存储到 `localStorage` 中，因此这个方法会返回一个字符串（如 `"john_doe"`）。

#### 3. `token()` 方法：
```js
token() {
  return localStorage.getItem("token");
}
```
- 从 `localStorage` 中获取名为 `"token"` 的键对应的值。
- 通常用于存储 JWT（JSON Web Token）或其他类型的认证令牌，用来验证用户身份。

---

### 总结：

`exists()` 方法的作用是：  
✅ **判断当前是否有有效的用户会话**，即：  
- 用户名和 token 都存在于本地存储中。  

这在前端开发中常用于判断用户是否已登录，从而决定是否允许访问受保护的路由或资源。

---

### 示例使用场景：

```js
if (session.exists()) {
  // 用户已登录，可以访问受保护的页面
} else {
  // 用户未登录，跳转到登录页
}
```


## 3. 微调后模型响应

```
推理过程：
步骤1: 分析Session类的定义和结构，发现存在一个exists方法。
步骤2: 查看exists方法内部逻辑，发现它通过username()和token()方法获取本地存储中的值，并进行判断。
步骤3: 结合代码逻辑推断出exists方法的功能是验证用户是否已登录。

exists方法用于检查当前会话是否有效。它通过调用username()和token()方法获取本地存储中的用户名和令牌，如果两者都存在，则返回true，表示会话有效；否则返回false。
```

### 对比分析

| 维度 | 基础模型 | 微调后模型 |
|------|---------|-----------|
| **响应长度** | 906 字符 | 238 字符 |
| **推理过程** | ❌ 无 | ✅ 包含步骤化推理（步骤1、步骤2、步骤3） |
| **代码上下文** | ✅ 详细解释 | ✅ 简洁准确 |
| **结构化输出** | ✅ 使用 Markdown 格式 | ✅ 清晰的推理步骤 |
| **实用性** | 信息量大但冗长 | 简洁高效，符合训练数据格式 |

**微调效果总结**：
- ✅ 微调后的模型能够按照训练数据的格式要求，提供结构化的推理过程
- ✅ 响应更加简洁高效，减少了冗余信息
- ✅ 保持了代码分析的准确性，同时提升了输出的规范性
- ✅ 符合项目要求的"包含推理过程"的数据格式
