# ThinkAi - Enterprise AI Framework

基于Python异步的企业级AI大模型集成框架 - **开箱即用,简单易用,功能全面**

## 特性

- **轻量零依赖** - 核心框架不依赖任何Web框架,完全脱离FastAPI
- **多模型支持** - 支持Ollama、OpenAI、通义千问、DeepSeek、Claude、Gemini等主流大模型
- **统一接口** - 一次配置,多模型自由切换
- **开箱即用** - 简单配置即可使用,无需复杂配置
- **符合OpenAI标准** - 采用OpenAI兼容的API格式
- **流式响应** - 支持SSE流式输出
- **会话管理** - 内置多轮对话上下文管理
- **RAG支持** - 3行代码实现检索增强生成
- **Agent系统** - 内置ReAct Agent,支持工具调用
- **中间件管道** - 日志、重试、缓存、限流
- **企业级性能** - 异步架构,连接池,自动重试

## 安装

```bash
# 基础安装 (轻量核心,无任何Web框架依赖)
pip install thinkai-framework

# Web开发支持
pip install thinkai-framework[web]

# 安装特定Provider
pip install thinkai-framework[ollama]
pip install thinkai-framework[openai]
pip install thinkai-framework[qwen]

# 安装全部依赖
pip install thinkai-framework[all]
```

## 快速开始

### 1. 最简使用(3行代码)

```python
from thinkai import ThinkAI

ai = ThinkAI(provider="ollama", model="llama3")
response = await ai.chat("你好")
print(response.content)
```

### 2. FastAPI集成

```python
from fastapi import FastAPI
from thinkai import ThinkAI

app = FastAPI()
ai = ThinkAI(provider="ollama", model="llama3")

@app.post("/chat")
async def chat(message: str):
    response = await ai.chat(message)
    return {"content": response.content}

# 启动: uvicorn main:app --reload
```

### 3. 多模型配置与切换

```python
from thinkai import ThinkAI

ai = ThinkAI(provider="ollama", model="llama3")

# 注册多个模型
ai.register_model("qwen", provider="qwen", model="qwen-turbo")
ai.register_model("deepseek", provider="deepseek", model="deepseek-chat")
ai.register_model("gpt4", provider="openai", model="gpt-4")

# 自由切换
response1 = await ai.chat("你好", model="llama3")
response2 = await ai.chat("你好", model="qwen")
response3 = await ai.chat("你好", model="deepseek")
response4 = await ai.chat("你好", model="gpt4")
```

### 4. 多轮对话(会话管理)

```python
ai = ThinkAI()

async with ai.session() as session:
    response1 = await session.chat("你好,我想学习Python")
    response2 = await session.chat("有什么好的学习路径?")
    response3 = await session.chat("推荐一些资源吧")
```

### 5. 流式响应

```python
ai = ThinkAI()

async for chunk in ai.chat_stream("讲一个故事"):
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### 6. RAG(检索增强生成)

```python
from thinkai import ThinkAI
from thinkai.rag import RAGPipeline

ai = ThinkAI()

# 3行代码实现RAG
rag = RAGPipeline(
    documents=["./docs", "./knowledge"],
    ai_client=ai,
    chunk_size=500,
)

# 查询
answer = await rag.query("ThinkAi框架支持哪些AI模型?")
print(answer)
```

### 7. Agent(智能体)

```python
from thinkai import ThinkAI
from thinkai.agent import ReActAgent, Tool

# 定义工具
@Tool(name="calculator", description="计算数学表达式")
def calculator(expression: str) -> str:
    return str(eval(expression))

@Tool(name="search", description="搜索信息")
async def search(query: str) -> str:
    # 实现搜索逻辑
    return "搜索结果"

ai = ThinkAI()

# 创建Agent
agent = ReActAgent(
    tools=[calculator, search],
    ai_client=ai,
    verbose=True,
)

# 运行任务
result = await agent.run("计算25*48,然后搜索Python的相关信息")
print(result)
```

## 支持的AI模型(开箱即用)

框架已内置所有主流大模型,支持以下Provider:

| Provider | 默认模型 | API地址 | 类型 | 获取API Key |
|----------|---------|---------|------|------------|
| **Ollama** | llama3 | http://localhost:11434 | 本地免费 | 无需Key |
| **OpenAI** | gpt-3.5-turbo | https://api.openai.com/v1 | 云端 | platform.openai.com |
| **DeepSeek** | deepseek-chat | https://api.deepseek.com/v1 | 云端免费 | platform.deepseek.com |
| **通义千问** | qwen-turbo | https://dashscope.aliyuncs.com | 云端 | dashscope.console.aliyun.com |
| **智谱GLM** | glm-4 | https://open.bigmodel.cn | 云端 | open.bigmodel.cn |
| **百度文心** | ernie-bot | https://qianfan.baidubce.com | 云端 | qianfan.cloud.baidu.com |
| **腾讯混元** | hunyuan | https://api.hunyuan.cloud.tencent.com | 云端 | cloud.tencent.com |
| **豆包ARK** | doubao-pro | https://ark.cn-beijing.volces.com | 云端 | console.volcengine.com |
| **Kimi** | moonshot-v1-8k | https://api.moonshot.cn/v1 | 云端 | platform.moonshot.cn |
| **MiniMax** | abab6-chat | https://api.minimax.chat/v1 | 云端 | api.minimax.chat |
| **Anthropic Claude** | claude-3-sonnet | https://api.anthropic.com | 云端 | console.anthropic.com |
| **Google Gemini** | gemini-pro | https://generativelanguage.googleapis.com | 云端 | ai.google.dev |

### 快速使用(复制即用)

```python
from thinkai import ThinkAI

# 本地模型(无需API Key)
ai = ThinkAI(provider="ollama", model="llama3")

# OpenAI GPT系列
ai = ThinkAI(provider="openai", api_key="your-key", model="gpt-4")

# DeepSeek(性价比高)
ai = ThinkAI(provider="deepseek", api_key="your-key")

# 通义千问(阿里云)
ai = ThinkAI(provider="qwen", api_key="your-key")

# 智谱GLM
ai = ThinkAI(provider="glm", api_key="your-key")

# 百度文心
ai = ThinkAI(provider="baidu", api_key="your-key")

# 腾讯混元
ai = ThinkAI(provider="tencent", api_key="your-key")

# 豆包(字节跳动)
ai = ThinkAI(provider="doubao", api_key="your-key")

# Kimi(月之暗面)
ai = ThinkAI(provider="kimi", api_key="your-key")

# MiniMax
ai = ThinkAI(provider="minimax", api_key="your-key")

# Anthropic Claude
ai = ThinkAI(provider="claude", api_key="your-key", model="claude-3-5-sonnet-20241022")

# Google Gemini
ai = ThinkAI(provider="gemini", api_key="your-key", model="gemini-pro")
```

## 项目结构

```
thinkai/
├── thinkai/
│   ├── __init__.py
│   ├── core/           # 核心模块
│   │   ├── client.py   # 统一客户端
│   │   ├── config.py   # 配置管理
│   │   └── models.py   # 数据模型
│   ├── providers/      # Provider实现
│   │   ├── base.py     # Provider基类
│   │   ├── registry.py # 注册表
│   │   ├── ollama.py   # Ollama
│   │   ├── openai.py   # OpenAI
│   │   ├── qwen.py     # 通义千问
│   │   └── deepseek.py # DeepSeek
│   ├── session/        # 会话管理
│   ├── prompt/         # Prompt模板
│   ├── middleware/     # 中间件
│   ├── rag/            # RAG模块
│   ├── agent/          # Agent模块
│   ├── streaming.py    # 流式处理
│   └── exceptions.py   # 异常定义
├── examples/           # 示例代码
├── config.example.yaml # 配置示例
├── .env.example        # 环境变量示例
└── pyproject.toml      # 项目配置
```

## 配置方式

### 方式1: 代码配置

```python
ai = ThinkAI(
    provider="ollama",
    model="llama3",
    temperature=0.7,
    max_tokens=2048,
    timeout=60,
)
```

### 方式2: 环境变量

```bash
export THINKAI_DEFAULT_PROVIDER=ollama
export THINKAI_DEFAULT_MODEL=llama3
export OPENAI_API_KEY=your_key_here
```

### 方式3: YAML配置文件

```yaml
default_provider: "ollama"
default_model: "llama3"

providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    api_base: "https://api.openai.com/v1"

models:
  llama3:
    provider: "ollama"
    model: "llama3"
    temperature: 0.7
```

```python
from thinkai.core.config import Settings

config = Settings.from_file("config.yaml")
ai = ThinkAI(config=config)
```

## 高级功能

### 中间件系统

```python
from thinkai.middleware import LoggingMiddleware, RetryMiddleware

ai = ThinkAI()
ai.add_middleware(LoggingMiddleware())
ai.add_middleware(RetryMiddleware(max_retries=3))
```

### Prompt模板

```python
from thinkai.prompt.template import PromptTemplate, prompt_manager

# 使用内置模板
template = prompt_manager.get("system_code")
prompt = template.format()

# 自定义模板
custom = PromptTemplate("将以下代码转换为$type: $code")
result = custom.format(type="Python", code="...")
```

### 自定义Provider

```python
from thinkai.providers.base import BaseProvider
from thinkai.providers.registry import register_provider

@register_provider("custom")
class CustomProvider(BaseProvider):
    name = "custom"
    default_model = "custom-model"
    
    async def chat(self, request):
        # 实现聊天逻辑
        pass
    
    async def chat_stream(self, request):
        # 实现流式聊天逻辑
        pass
```

## 企业级特性

- **异步架构** - 全面使用async/await,高性能
- **连接池** - HTTP连接复用
- **自动重试** - 失败自动重试,指数退避
- **错误处理** - 完善的异常体系
- **类型安全** - 完整的Type Hints
- **日志记录** - 结构化日志支持
- **监控指标** - 集成Prometheus(规划中)
- **负载均衡** - 多模型路由(规划中)

## 文档

完整文档请访问: [https://thinkai.readthedocs.io](https://thinkai.readthedocs.io)

## 示例

运行示例代码:

```bash
# 基础使用
python examples/basic_usage.py

# FastAPI集成
python examples/fastapi_demo.py

# RAG示例
python examples/rag_example.py

# Agent示例
python examples/agent_example.py
```

## 贡献

欢迎提交Issue和Pull Request!

## 许可证

MIT License
