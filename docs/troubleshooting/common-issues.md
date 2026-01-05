# 常见问题与解决方案

本文档列出使用系统时的常见问题及解决方案。

## 配置相关错误

### 错误 1: SettingsError 解析配置失败

**错误信息：**
```
pydantic_settings.exceptions.SettingsError: error parsing value for field 
"qa_types" from source "EnvSettingsSource"
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**原因：** 环境变量中有空的或格式不正确的配置。

**解决方案：**

```bash
# 方案1: 检查并删除错误的环境变量
env | grep GENERATOR_QA_TYPES
unset GENERATOR_QA_TYPES

# 方案2: 检查 .env 文件
cat .env | grep GENERATOR_QA_TYPES
# 如果有这一行且为空，删除它或注释掉

# 方案3: 重新运行
python main.py auto-discover -s 金融科技 --auto-generate
```

### 错误 2: API Key 未设置

**错误信息：**
```
LLM API 密钥未设置，请在 .env 文件中配置 LLM_API_KEY
```

**解决方案：**

```bash
# 创建 .env 文件
cp config.example.env .env

# 编辑并填入 API Key
vim .env
# 设置: LLM_API_KEY=your_key_here
```

## GitHub API 相关错误

### 错误 3: API rate limit exceeded

**错误信息：**
```
403 Client Error: rate limit exceeded
```

**原因：** GitHub API 请求限额已用完（无 Token: 60次/小时）。

**解决方案：**

```bash
# 配置 GitHub Token
export GITHUB_TOKEN=ghp_your_token_here

# 或在 .env 文件中添加
echo "GITHUB_TOKEN=ghp_your_token_here" >> .env
```

获取 Token: https://github.com/settings/tokens（权限只需勾选 `public_repo`）

配置后限额提升至 5000次/小时。

### 错误 4: 搜索结果为空

**症状：**
```
共找到 0 个唯一仓库
```

**解决方案：**

```bash
# 1. 检查场景名称
python main.py auto-discover --list-scenarios

# 2. 降低 Stars 门槛
python main.py auto-discover -s 金融科技 --min-stars 50

# 3. 尝试不同的场景
python main.py auto-discover -s API服务 -n 10

# 4. 检查网络连接
ping api.github.com
```

## 下载相关错误

### 错误 5: Git clone 失败

**错误信息：**
```
fatal: destination path already exists
```

**解决方案：**

```bash
# 删除已存在的目录
rm -rf downloaded_repos/<repo_name>

# 或使用不同的下载目录
python main.py auto-discover -s 金融科技 -d new_repos --auto-generate
```

### 错误 6: 权限拒绝

**错误信息：**
```
fatal: could not read from remote repository
```

**原因：** 仓库可能是私有的或已被删除。

**解决方案：** 系统会自动跳过无法访问的仓库，检查报告中的错误记录。

## 数据生成相关错误

### 错误 7: LLM 生成失败

**错误信息：**
```
Error generating QA: API call failed
```

**可能原因：**
1. API Key 无效或过期
2. 账户余额不足
3. 网络连接问题
4. API 服务暂时不可用

**解决方案：**

```bash
# 1. 检查 API Key
python -c "import os; print(os.getenv('LLM_API_KEY', '未设置')[:10] + '...')"

# 2. 测试 API 连接
python -c "
from dashscope import Generation
response = Generation.call(model='qwen-turbo', prompt='你好')
print('API 状态:', response.status_code)
"

# 3. 检查账户状态
# 访问 https://dashscope.console.aliyun.com/
```

### 错误 8: JSON 解析失败

**错误信息：**
```
无法解析 JSON 响应
```

**原因：** LLM 返回的内容格式不正确。

**解决方案：** 这是正常现象，系统会自动重试。如果错误率过高：

```bash
# 检查错误率
./scripts/monitoring/check_error_rate.sh

# 如果错误率 > 15%，考虑更换模型
# 在 .env 中设置：LLM_MODEL_NAME=qwen-plus
```

## 数据验证相关错误

### 错误 9: 数据格式不正确

**错误信息：**
```
Invalid data format: missing required field 'messages'
```

**解决方案：**

```bash
# 重新转换数据格式
python scripts/data_processing/convert_to_dashscope.py \
    input.alpaca -o output.jsonl

# 验证数据
python scripts/data_processing/validate_dashscope_data.py output.jsonl
```

### 错误 10: 数据量不足

**错误信息：**
```
训练数据量不足，最少需要 50 条
```

**解决方案：**
1. 增加处理的代码仓库数量
2. 增加 `--max-files` 参数
3. 移除 `--max-qa-per-repo` 限制

## 微调相关错误

### 错误 11: 微调任务创建失败

**错误信息：**
```
Failed to create fine-tuning job
```

**可能原因：**
1. 数据格式不正确
2. 数据量不满足要求
3. 账户权限问题

**解决方案：**

```bash
# 1. 验证数据格式
python scripts/data_processing/validate_dashscope_data.py train.jsonl

# 2. 检查数据量
wc -l train.jsonl

# 3. 检查账户状态
# 访问 DashScope 控制台
```

### 错误 12: 微调训练失败

**解决方案：**

```bash
# 查看任务详情
python scripts/finetuning/monitor_finetune.py <job_id>

# 常见原因：
# - 数据质量问题：重新清洗数据
# - 超参数问题：减小 learning rate
# - 资源问题：联系 DashScope 支持
```

## 环境相关问题

### 错误 13: 主脚本和子脚本使用不同的 Python 环境

**症状：**
```
✅ dashscope SDK 已安装  # 主脚本检查通过
...
❌ 错误: 未安装 dashscope SDK  # 子脚本报错
```

**解决方案：**

```bash
# 确保在虚拟环境中运行
source venv/bin/activate

# 重新安装依赖
pip install dashscope pyyaml
```

详细信息请参考 [安装部署指南](../getting-started/installation.md)。

## 获取帮助

如果以上方案都无法解决问题：

1. 查看完整日志：`cat batch_generate.log`
2. 在项目仓库创建 Issue
3. 提供错误信息和运行环境

## 相关文档

- [FAQ](faq.md) - 常见问题解答
- [调试指南](debugging.md) - 详细调试方法
- [安装部署](../getting-started/installation.md) - 环境配置

