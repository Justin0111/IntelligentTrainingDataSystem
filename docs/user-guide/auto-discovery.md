# 自动发现功能指南

本文档介绍如何使用自动发现功能，从 GitHub 自动搜索、下载优质代码仓库并生成训练数据。

## 功能概述

**自动发现功能**可以：
1. ✅ 根据业务场景、技术栈自动搜索 GitHub 仓库
2. ✅ 按 Stars、更新时间等指标筛选高质量仓库
3. ✅ 自动下载选中的仓库
4. ✅ 一键生成训练数据集

**无需手动查找和下载仓库！**

## 快速开始

### 步骤 1: 查看可用场景

```bash
python main.py auto-discover --list-scenarios
```

**输出示例：**
```
可用业务场景:

┌─────────┬────────────────────────┬──────┐
│ 场景名称 │ 描述                    │ 语言 │
├─────────┼────────────────────────┼──────┤
│ 金融科技 │ 支付系统、交易平台...   │ python │
│ 电商系统 │ 电商平台、购物车...     │ 不限 │
│ 微服务架构│ 微服务、API网关...     │ 不限 │
└─────────┴────────────────────────┴──────┘
```

### 步骤 2: 搜索并下载仓库

```bash
python main.py auto-discover \
    --scenario 金融科技 \
    --max-repos 5 \
    --auto-generate
```

### 步骤 3: 查看结果

```bash
ls output/auto_discovered/
cat output/auto_discovered/discovery_report_*.md
```

## 命令参数详解

### 主要参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--scenario` | `-s` | 业务场景（可多次指定） | 无 |
| `--tech-stack` | `-t` | 技术栈（可多次指定） | 无 |
| `--language` | `-l` | 编程语言 | 无 |
| `--max-repos` | `-n` | 每个场景最大仓库数 | 10 |
| `--min-stars` | 无 | 最小 Star 数 | 100 |
| `--download-dir` | `-d` | 下载目录 | `downloaded_repos` |
| `--output` | `-o` | 数据输出目录 | `output/auto_discovered` |
| `--auto-generate` | 无 | 自动执行数据生成 | False |
| `--max-qa-per-repo` | 无 | 每个仓库最大 QA 数 | 50 |
| `--format` | `-f` | 输出格式 | `alpaca` |
| `--split` | 无 | 划分训练/验证/测试集 | False |

### 查询参数

| 参数 | 说明 |
|------|------|
| `--list-scenarios` | 列出所有可用场景 |
| `--list-tech-stacks` | 列出所有可用技术栈 |

## 使用示例

### 查看可用选项

```bash
# 查看所有业务场景
python main.py auto-discover --list-scenarios

# 查看所有技术栈
python main.py auto-discover --list-tech-stacks
```

### 按场景搜索（仅搜索不下载）

```bash
python main.py auto-discover --scenario 金融科技 -n 10
```

### 单个场景自动生成

```bash
python main.py auto-discover \
    --scenario 电商系统 \
    --max-repos 5 \
    --auto-generate
```

### 自动生成并划分数据集

```bash
python main.py auto-discover \
    --scenario 金融科技 \
    --max-repos 5 \
    --auto-generate \
    --split
```

### 多个场景组合

```bash
python main.py auto-discover \
    -s 金融科技 \
    -s 电商系统 \
    -s 微服务架构 \
    -n 3 \
    --auto-generate
```

### 按技术栈搜索

```bash
# 搜索 Python Web 项目
python main.py auto-discover \
    --tech-stack "Python Web" \
    -n 5 \
    --auto-generate

# 搜索 Go 微服务项目
python main.py auto-discover \
    -t "Go微服务" \
    -n 5 \
    --auto-generate
```

### 场景 + 技术栈组合

```bash
python main.py auto-discover \
    -s 金融科技 \
    -t "Python Web" \
    -n 5 \
    --auto-generate
```

### 指定编程语言

```bash
python main.py auto-discover \
    -s API服务 \
    --language python \
    -n 10 \
    --auto-generate
```

### 高星仓库筛选

```bash
python main.py auto-discover \
    -s 机器学习 \
    --min-stars 1000 \
    -n 5 \
    --auto-generate
```

## 预定义场景

系统内置了 10+ 个预定义场景：

| 场景 | 描述 | 推荐语言 |
|------|------|----------|
| 金融科技 | 支付系统、交易平台、风控系统 | Python |
| 电商系统 | 电商平台、购物车、订单管理 | 不限 |
| 微服务架构 | 微服务、API 网关、服务发现 | 不限 |
| 数据处理 | ETL、数据管道、数据分析 | Python |
| API服务 | REST API、GraphQL、RPC | 不限 |
| 机器学习 | ML 框架、模型训练、推理服务 | Python |
| DevOps工具 | CI/CD、容器、监控 | Go |
| 区块链 | 区块链、智能合约 | Rust/Go |
| 实时系统 | 实时数据、流处理、消息队列 | 不限 |
| 安全工具 | 安全扫描、认证、加密 | Python |

## 预定义技术栈

| 技术栈 | 关键词 |
|--------|--------|
| Python Web | Django, FastAPI, Flask |
| Node.js | Express, NestJS, Koa |
| Go微服务 | gin, gRPC, microservice |
| Java Spring | Spring Boot, Spring Cloud |
| React生态 | React, Next.js, Redux |
| Vue生态 | Vue, Nuxt, Vuex |

## 输出文件说明

```
output/auto_discovered/
├── auto_discovered_qa_*.alpaca          # QA 数据集
├── auto_discovered_qa_*_train.alpaca    # 训练集 (使用 --split 时)
├── auto_discovered_qa_*_valid.alpaca    # 验证集
├── auto_discovered_qa_*_test.alpaca     # 测试集
├── discovery_report_*.json              # JSON 格式报告
└── discovery_report_*.md                # Markdown 格式报告
```

## 已下载的仓库示例

系统已成功下载并处理了 **35 个高质量开源仓库**，覆盖多个业务场景和技术栈。以下是部分仓库列表：

### 按语言分类

#### Python 项目 (6个)
| 仓库名称 | Stars | 描述 | 场景 |
|---------|-------|------|------|
| [stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) | 159,630 | Stable Diffusion web UI | 机器学习 |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | 98,958 | 强大的模块化扩散模型 GUI | 机器学习 |
| [ragflow](https://github.com/infiniflow/ragflow) | 70,845 | 开源 RAG 引擎 | AI/LLM |
| [litellm](https://github.com/BerriAI/litellm) | 33,245 | LLM API 代理服务器 | API服务 |
| [khoj](https://github.com/khoj-ai/khoj) | 32,093 | AI 第二大脑 | AI/LLM |
| [pathway](https://github.com/pathwaycom/pathway) | 56,084 | Python ETL 流处理框架 | 数据处理 |

#### TypeScript/JavaScript 项目 (11个)
| 仓库名称 | Stars | 描述 | 场景 |
|---------|-------|------|------|
| [open-webui](https://github.com/open-webui/open-webui) | 119,628 | 用户友好的 AI 界面 | AI/LLM |
| [firecrawl](https://github.com/firecrawl/firecrawl) | 72,878 | Web 数据 API for AI | 数据处理 |
| [lobe-chat](https://github.com/lobehub/lobe-chat) | 69,767 | 开源 AI Agent 工作区 | AI/LLM |
| [ragflow](https://github.com/infiniflow/ragflow) | 70,845 | RAG 引擎 | AI/LLM |
| [astro](https://github.com/withastro/astro) | 55,294 | Web 框架 | Web框架 |
| [FastGPT](https://github.com/labring/FastGPT) | 26,760 | 知识库平台 | AI/LLM |
| [shardeum](https://github.com/shardeum/shardeum) | 31,655 | EVM 自动扩展区块链 | 区块链 |
| [activepieces](https://github.com/activepieces/activepieces) | 20,203 | AI 工作流自动化 | 自动化 |
| [stagehand](https://github.com/browserbase/stagehand) | 19,922 | AI 浏览器自动化框架 | 自动化 |
| [bruno](https://github.com/usebruno/bruno) | 39,612 | 开源 API 客户端 | API服务 |
| [yaak](https://github.com/mountain-loop/yaak) | 17,293 | 桌面 API 客户端 | API服务 |

#### Rust 项目 (3个)
| 仓库名称 | Stars | 描述 | 场景 |
|---------|-------|------|------|
| [union](https://github.com/unionlabs/union) | 74,426 | 零知识桥接协议 | 区块链 |
| [hyperswitch](https://github.com/juspay/hyperswitch) | 39,300 | 开源支付交换机 | 金融科技 |
| [linera-protocol](https://github.com/linera-io/linera-protocol) | 31,958 | Linera 协议 | 区块链 |

#### 其他语言项目
| 语言 | 仓库数 | 代表项目 |
|------|--------|----------|
| Jupyter Notebook | 5 | ML-For-Beginners, LLMs-from-scratch, openai-cookbook |
| C# | 2 | agents, eShop |
| Go | 1 | ntfy |
| Elixir | 1 | anoma |
| Dart | 1 | opensource-ecommerce-mobile-app |
| C++ | 1 | windhawk |
| PLpgSQL | 1 | Tigshop |

### 按业务场景分类

#### AI/LLM 相关 (12个)
- open-webui, lobe-chat, ragflow, FastGPT, khoj, litellm, stable-diffusion-webui, ComfyUI, LLMs-from-scratch, openai-cookbook, Prompt-Engineering-Guide, llm-app

#### 电商系统 (3个)
- eShop, opensource-ecommerce-mobile-app, Tigshop

#### 金融科技 (1个)
- hyperswitch

#### 区块链 (4个)
- union, linera-protocol, shardeum, anoma

#### API服务/工具 (4个)
- bruno, yaak, firecrawl, maxun

#### 数据处理 (2个)
- pathway, data-engineering-zoomcamp

#### DevOps/工具 (2个)
- 90DaysOfDevOps, ntfy

#### Web框架 (1个)
- astro

#### 自动化 (2个)
- activepieces, stagehand

#### 其他 (4个)
- agents, windhawk, Some-Many-Books, ML-For-Beginners

### 统计数据

- **总仓库数**: 35
- **总 Stars**: 超过 1,200,000
- **语言分布**: TypeScript (9), Python (6), Jupyter Notebook (5), Rust (3), 其他 (12)
- **平均 Stars**: 约 34,000
- **最新更新**: 2026-01-04

这些仓库已成功下载到 `downloaded_repos/` 目录，可用于生成高质量的训练数据。仓库元数据信息保存在 `downloaded_repos/repos_metadata.json` 文件中。

## 常见问题

### Q: 如何提高 GitHub API 限额？

**A:** 设置 GitHub Token：

```bash
export GITHUB_TOKEN='your_token_here'
```

Token 可以将限额从 60/小时提高到 5000/小时。

### Q: 下载的仓库存储在哪里？

**A:** 默认存储在 `downloaded_repos/` 目录，可通过 `--download-dir` 参数修改。

### Q: 如何只搜索不下载？

**A:** 不使用 `--auto-generate` 参数即可：

```bash
python main.py auto-discover -s 金融科技 -n 10
```

### Q: 下载失败怎么办？

**A:**
1. 检查网络连接
2. 确认 GitHub Token 有效
3. 仓库可能被删除或设为私有

## 相关文档

- [批量处理指南](batch-processing.md) - 处理本地仓库
- [微调指南](finetuning-guide.md) - 使用数据微调模型

