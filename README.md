# ThinkAi - Enterprise AI Framework

基于Python异步的企业级AI大模型集成框架 - **开箱即用,简单易用,功能全面**

[![Gitee](https://img.shields.io/badge/Gitee-ThinkAi-red)](https://gitee.com/hongxinge/think-ai)
[![GitHub](https://img.shields.io/badge/GitHub-ThinkAi-black)](https://github.com/hongxinge/ThinkAi)
[![PyPI](https://img.shields.io/pypi/v/thinkai-framework)](https://pypi.org/project/thinkai-framework/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

- 🏠 Gitee: https://gitee.com/hongxinge/think-ai
- 🌐 GitHub: https://github.com/hongxinge/ThinkAi
- 📦 PyPI: https://pypi.org/project/thinkai-framework/

## 特性

- **轻量零依赖** - 核心框架不依赖任何Web框架,完全脱离FastAPI
- **OpenAI SDK底层** - OpenAI及兼容Provider使用官方OpenAI Python SDK作为底层传输层,稳定可靠
- **多模型支持** - 支持Ollama、OpenAI、通义千问、DeepSeek、Claude、Gemini等主流大模型
- **统一接口** - 一次配置,多模型自由切换
- **开箱即用** - 简单配置即可使用,无需复杂配置
- **同步/异步双模式** - 异步优先,同时提供同步API,简单脚本无需async/await
- **符合OpenAI标准** - 采用OpenAI兼容的API格式
- **流式响应** - 支持SSE流式输出,Agent支持真正的流式Function Calling
- **会话管理** - 内置多轮对话上下文管理
- **RAG支持** - 内置Embedding + 向量检索,3行代码实现检索增强生成
- **Agent系统** - 内置ReAct Agent、Function Calling Agent、流式Function Calling Agent
- **Skill系统** - 9大内置Skill(搜索/代码/数学/文件/数据库/API/图像/文本/系统),安全沙箱执行
- **记忆系统** - 长期记忆、跨会话记忆、自动遗忘、重要性衰减
- **多Agent协作** - Sequential/Parallel/Hierarchical三种协作模式
- **MCP支持** - 轻量级Model Context Protocol客户端
- **中间件管道** - 日志、重试(真正有效),可扩展
- **缓存层** - LRU内存缓存/文件缓存,减少重复API调用
- **结构化输出** - Pydantic模型约束LLM输出,自动JSON解析与验证
- **速率限制** - Token Bucket限流 + 并发控制,企业级流量管理
- **追踪可观测** - TraceSpan链路追踪,Console/JSON导出
- **Agent状态持久化** - 保存/恢复Agent执行状态,支持断点续跑
- **插件系统** - 动态加载外部Skill/Provider/Middleware,可扩展
- **@tool装饰器** - 一行代码创建Tool,自动推断参数Schema
- **16种Prompt模板** - CoT/Few-Shot/翻译/代码审查/测试生成等
- **企业级安全** - 代码沙箱执行、文件路径限制、环境变量访问控制
- **企业级性能** - 异步架构,连接池,自动重试
- **CLI工具** - 命令行直接对话

## 安装

```bash
# 基础安装 (轻量核心,无任何Web框架依赖)
pip install thinkai-framework

# Web开发支持（安装FastAPI依赖，用于构建API服务）
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

### 2. 同步模式(无需async/await)

```python
from thinkai import SyncThinkAI

ai = SyncThinkAI(provider="ollama", model="llama3")
response = ai.chat("你好")
print(response.content)
```

### 3. CLI命令行

```bash
# 查看版本
thinkai version

# 直接对话
thinkai chat "你好" --provider ollama

# 查看可用Provider
thinkai providers
```

### 4. FastAPI集成

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

### 5. 多模型配置与切换

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
```

### 6. 多轮对话(会话管理)

```python
ai = ThinkAI()

async with ai.session() as session:
    response1 = await session.chat("你好,我想学习Python")
    response2 = await session.chat("有什么好的学习路径?")
    response3 = await session.chat("推荐一些资源吧")
```

### 7. 流式响应

```python
ai = ThinkAI()

async for chunk in ai.chat_stream("讲一个故事"):
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### 8. RAG(检索增强生成)

```python
from thinkai import ThinkAI
from thinkai.rag import RAGPipeline

ai = ThinkAI(provider="ollama")

# 创建RAG Pipeline(自动使用Ollama Embedding)
rag = RAGPipeline(
    documents=["./docs", "./knowledge"],
    ai_client=ai,
)

# 索引文档
await rag.index()

# 查询
answer = await rag.query("ThinkAi框架支持哪些AI模型?")
print(answer)
```

> **Embedding说明**: 默认使用轻量级哈希Embedding(开箱即用,无需额外模型)。配置Ollama后自动使用`nomic-embed-text`模型生成高质量向量。

### 9. Function Calling Agent(函数调用智能体)

```python
from thinkai import ThinkAI
from thinkai.agent import FunctionCallingAgent
from thinkai.skill import MathSkill, CodeSkill

ai = ThinkAI(provider="openai", api_key="your-key")

# 注意: 使用 + 拼接多个Skill的工具列表
agent = FunctionCallingAgent(
    name="math-coder",
    tools=MathSkill().get_tools() + CodeSkill().get_tools(),
    ai_client=ai,
    verbose=True,
)

result = await agent.run("计算123*456,然后用Python写一个斐波那契数列函数")
print(result)
```

### 10. 记忆系统

```python
from thinkai import ThinkAI
from thinkai.memory import MemoryManager, FileMemoryStore

ai = ThinkAI(provider="ollama")

# 创建记忆管理器(默认使用文件存储)
memory = MemoryManager(
    store=FileMemoryStore(base_path="./my_memory"),
    max_memories=100,
    enable_forgetting=True,
)

# 记住信息
await memory.remember("用户喜欢Python编程", memory_type="preference", importance=0.8)
await memory.remember("项目使用FastAPI框架", memory_type="fact", importance=0.9)

# 回忆相关记忆
results = await memory.recall("编程语言")
for item in results:
    print(f"[{item.memory_type}] {item.content} (重要性: {item.importance})")

# 构建上下文Prompt(自动注入到对话中)
context = await memory.build_context_prompt("Python开发", max_tokens=500)
```

### 11. 多Agent协作

```python
from thinkai import ThinkAI
from thinkai.agent import ReActAgent, FunctionCallingAgent
from thinkai.agent.orchestrator import MultiAgentOrchestrator, AgentRole
from thinkai.skill import MathSkill, WebSearchSkill

ai = ThinkAI(provider="openai", api_key="your-key")

orchestrator = MultiAgentOrchestrator(ai_client=ai)

# 添加Agent
orchestrator.add_agent(
    agent=FunctionCallingAgent(
        name="researcher",
        tools=WebSearchSkill().get_tools(),
        ai_client=ai,
    ),
    role=AgentRole.SPECIALIST,
    capabilities=["search", "research"],
)

orchestrator.add_agent(
    agent=FunctionCallingAgent(
        name="analyzer",
        tools=MathSkill().get_tools(),
        ai_client=ai,
    ),
    role=AgentRole.WORKER,
    capabilities=["math", "analysis"],
)

# 顺序执行
result = await orchestrator.run(
    task=["搜索AI最新进展", "分析搜索结果中的关键数据"],
    mode="sequential",
)

# 并行执行
result = await orchestrator.run(
    task=["搜索AI进展", "搜索量子计算进展", "搜索区块链进展"],
    mode="parallel",
)

# 层级执行(协调者自动分解任务)
result = await orchestrator.run(
    task="调研AI行业现状并生成分析报告",
    mode="hierarchical",
)
```

### 12. MCP(Model Context Protocol)

```python
from thinkai import ThinkAI
from thinkai.mcp import MCPAdapter, MCPRegistry

ai = ThinkAI(provider="openai", api_key="your-key")

adapter = MCPAdapter()

# 添加MCP Server(使用预定义配置)
fs_config = MCPRegistry.filesystem("/workspace")
adapter.add_server(**fs_config)

# 连接并创建Agent
await adapter.connect_all()
agent = adapter.create_agent(ai_client=ai)

result = await agent.run("读取/workspace/readme.md文件内容")
print(result)

# 使用完毕后关闭
await adapter.close_all()
```

### 13. Agent生命周期钩子

```python
from thinkai import ThinkAI
from thinkai.agent import FunctionCallingAgent

ai = ThinkAI(provider="openai", api_key="your-key")

agent = FunctionCallingAgent(
    ai_client=ai,
    on_start=lambda task: print(f"🚀 开始任务: {task}"),
    on_tool_call=lambda name, args: print(f"🔧 调用工具: {name}"),
    on_tool_result=lambda name, result: print(f"✅ 工具结果: {name}"),
    on_finish=lambda result: print(f"🎯 任务完成"),
    on_error=lambda e: print(f"❌ 错误: {e}"),
)

result = await agent.run("计算2的10次方")
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
│   │   ├── base.py     # Provider基类(连接池,重试)
│   │   ├── registry.py # 注册表
│   │   ├── ollama.py   # Ollama
│   │   ├── openai.py   # OpenAI
│   │   ├── openai_compatible.py  # OpenAI兼容(9大国产模型)
│   │   └── shortcuts.py # 快捷Provider注册
│   ├── session/        # 会话管理
│   ├── prompt/         # Prompt模板
│   ├── middleware/     # 中间件(日志,重试)
│   ├── rag/            # RAG模块
│   │   ├── pipeline.py # RAG Pipeline
│   │   ├── embedding.py # Embedding(哈希/Ollama/OpenAI)
│   │   ├── vector_store.py # 向量存储抽象
│   │   ├── chroma_store.py # ChromaDB实现
│   │   ├── document_loader.py # 文档加载器
│   │   └── text_splitter.py # 文本分割器
│   ├── agent/          # Agent模块
│   │   ├── base.py     # Agent基类(生命周期钩子)
│   │   ├── react.py    # ReAct Agent
│   │   ├── function_calling.py  # Function Calling Agent
│   │   ├── streaming_fc.py # 流式Function Calling Agent
│   │   ├── orchestrator.py # 多Agent协作
│   │   └── tool.py     # Tool定义
│   ├── skill/          # Skill系统
│   │   ├── __init__.py # Skill基类和内置Skill(安全沙箱)
│   │   └── builtin_skills.py # 更多内置Skill
│   ├── memory/         # 记忆系统
│   ├── mcp/            # MCP协议支持
│   ├── cache/          # 缓存层(Memory/File)
│   ├── structured/     # 结构化输出
│   ├── tracing/        # 链路追踪
│   ├── plugin/         # 插件系统
│   ├── sync.py         # 同步API封装
│   ├── cli.py          # CLI命令行工具
│   ├── streaming.py    # 流式处理
│   └── exceptions.py   # 异常定义
├── tests/              # 测试(223个测试用例)
├── pyproject.toml      # 项目配置
└── README.md
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

## 安全特性

ThinkAi框架内置多层安全保护,适合企业级使用:

- **代码执行沙箱** - CodeSkill使用AST验证+受限内置函数,禁止import、文件访问、系统调用
- **数学表达式安全** - MathSkill使用AST解析,只允许数学运算符,杜绝eval()注入
- **文件路径限制** - FileSkill默认只允许访问当前目录,可配置allowed_dirs
- **环境变量保护** - SystemSkill只允许读取指定前缀的环境变量(默认THINKAI_/APP_/PATH)
- **目录访问控制** - SystemSkill的list_directory同样受路径限制

```python
from thinkai.skill import FileSkill, CodeSkill, SystemSkill

# 配置文件访问范围
file_skill = FileSkill(allowed_dirs=["/data", "/workspace"])

# 配置环境变量访问前缀
system_skill = SystemSkill(allowed_env_prefixes=["MYAPP_", "THINKAI_"])

# 代码沙箱自动阻止危险操作
code_skill = CodeSkill()
# 以下代码会被阻止: import os, open(), exec(), eval()
```

## 高级功能

### 中间件系统(真正有效的重试)

```python
from thinkai.middleware import LoggingMiddleware, RetryMiddleware

ai = ThinkAI()
ai.add_middleware(LoggingMiddleware())
ai.add_middleware(RetryMiddleware(max_retries=3, backoff_factor=2.0))
# RetryMiddleware现在真正有效 - 在ThinkAI.chat()中实现重试循环
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

### 缓存层(减少重复API调用)

```python
from thinkai import ThinkAI
from thinkai.cache import CacheMiddleware, MemoryCache, cached

ai = ThinkAI()

# 方式1: 中间件缓存(自动缓存chat请求)
ai.add_middleware(CacheMiddleware(ttl=300))

# 方式2: 独立缓存
cache = MemoryCache(max_size=1000, default_ttl=3600)
await cache.set("query:hello", {"content": "你好!"})
result = await cache.get("query:hello")

# 方式3: @cached装饰器
@cached(ttl=300)
async def ask_ai(question: str):
    return await ai.chat(question)
```

### 结构化输出(Pydantic模型约束)

```python
from thinkai import ThinkAI
from pydantic import BaseModel, Field

ai = ThinkAI(provider="openai", api_key="your-key")

class PersonInfo(BaseModel):
    name: str = Field(description="人名")
    age: int = Field(description="年龄")
    occupation: str = Field(description="职业")

# 自动生成Schema Prompt + JSON解析 + Pydantic验证
person = await ai.structured.extract(
    "张三今年28岁,是一名软件工程师",
    PersonInfo,
)
print(person.name)        # 张三
print(person.age)         # 28
print(person.occupation)  # 软件工程师
```

### @tool装饰器(一行创建工具)

```python
from thinkai.agent import FunctionCallingAgent
from thinkai.agent.tool import tool

@tool
def search_web(query: str, num_results: int = 5) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

@tool(name="calculator", description="Perform calculations")
def calculate(expression: str) -> str:
    """Calculate a math expression."""
    return str(eval(expression))

agent = FunctionCallingAgent(tools=[search_web, calculate], ai_client=ai)
```

### 速率限制(企业级流量管理)

```python
from thinkai import ThinkAI
from thinkai.middleware.rate_limit import RateLimitMiddleware

ai = ThinkAI()

# 60请求/分钟, 最大10并发
ai.add_middleware(RateLimitMiddleware(
    requests_per_minute=60,
    burst=10,
    max_concurrent=10,
))
```

### 链路追踪(可观测性)

```python
from thinkai.tracing import get_tracer, ConsoleTraceExporter, TraceCallback

tracer = get_tracer()
tracer.add_exporter(ConsoleTraceExporter())

# 方式1: 上下文管理器
async with tracer.trace("chat_request", model="gpt-4"):
    response = await ai.chat("你好")

# 方式2: Agent生命周期回调
callback = TraceCallback(tracer)
agent = FunctionCallingAgent(
    ai_client=ai,
    on_start=callback.on_start,
    on_tool_call=callback.on_tool_call,
    on_tool_result=callback.on_tool_result,
    on_finish=callback.on_finish,
    on_error=callback.on_error,
)
```

### Agent状态持久化(断点续跑)

```python
from thinkai.agent import FunctionCallingAgent
from thinkai.agent.state import PersistentAgentMixin, FileStateStorage

# 创建带持久化的Agent
class MyAgent(FunctionCallingAgent, PersistentAgentMixin):
    pass

agent = MyAgent(ai_client=ai)
storage = FileStateStorage(storage_dir="./agent_states")

# 保存状态
state_id = await agent.save_state(storage)

# 恢复状态(断点续跑)
await agent.restore_state(state_id, storage)
result = await agent.run("继续之前的任务")
```

### 插件系统(动态扩展)

```python
from thinkai.plugin import thinkai_plugin, plugin_manager

# 定义插件
@thinkai_plugin(name="my-skill", version="1.0", description="自定义Skill", plugin_type="skill")
class MyCustomSkill:
    def get_tools(self):
        return [...]

# 安装到框架
plugin_manager.install_skill("my-skill", skill_manager)
```

### 更多Prompt模板

```python
from thinkai.prompt.template import prompt_manager

# Chain-of-Thought推理
prompt = prompt_manager.format("chain_of_thought", question="为什么天空是蓝色的?")

# Few-Shot学习
prompt = prompt_manager.format("few_shot", examples="Q:2+2? A:4", question="Q:3+3?")

# 代码审查
prompt = prompt_manager.format("code_review", language="Python", code="def add(a,b): return a+b")

# 翻译
prompt = prompt_manager.format("translate", source_lang="English", target_lang="Chinese", text="Hello")

# 测试生成
prompt = prompt_manager.format("test_generation", language="Python", code="def add(a,b): return a+b")
```

## 企业级特性

- **异步架构** - 全面使用async/await,高性能
- **同步封装** - SyncThinkAI让简单脚本无需async/await
- **连接池** - HTTP连接复用,可配置连接池大小
- **自动重试** - 真正有效的重试机制,指数退避
- **缓存层** - LRU内存缓存/文件缓存,减少API调用
- **速率限制** - Token Bucket限流 + 并发控制
- **链路追踪** - TraceSpan链路追踪,Console/JSON导出
- **安全沙箱** - 代码执行、文件访问、环境变量多层保护
- **结构化输出** - Pydantic模型约束LLM输出
- **状态持久化** - Agent断点续跑
- **插件系统** - 动态加载Skill/Provider/Middleware
- **错误处理** - 完善的异常体系
- **类型安全** - 完整的Type Hints + Pydantic验证
- **日志记录** - 结构化日志支持
- **生命周期钩子** - Agent执行过程可观测
- **CLI工具** - 命令行直接使用

## 文档

完整文档请访问: [https://thinkai.readthedocs.io](https://thinkai.readthedocs.io)

## 贡献

欢迎提交Issue和Pull Request!

## 许可证

MIT License
