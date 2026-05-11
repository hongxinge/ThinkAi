# 一行代码调用13个AI大模型，这个Python框架太香了！

## 引言

你是否曾经被AI大模型的接入折磨过？

- 配置OpenAI API，再配DeepSeek，又配通义千问...
- 每个API格式都不一样，请求参数、响应解析全要重写
- 想换个模型？改代码改到怀疑人生！

今天给大家分享一个开源项目：**ThinkAi**，帮你终结这一切！

## 什么是ThinkAi？

ThinkAi 是一个基于Python异步的企业级AI大模型集成框架，让你**一行代码就能调用13个主流AI大模型**。

```python
from thinkai import ThinkAI

# 一行代码，接入OpenAI
ai = ThinkAI(provider="openai", api_key="your-key")
response = await ai.chat("你好")
print(response.content)

# 换成DeepSeek？只需改一行！
ai = ThinkAI(provider="deepseek", api_key="your-key")
```

就是这么简单！

## 核心优势

**一行代码接入**：`provider="模型名"` 即可使用，无需重复配置

**13个主流模型**：OpenAI、DeepSeek、通义千问、GLM、百度文心、腾讯混元、豆包、Kimi、MiniMax、Claude、Gemini、Ollama、任意OpenAI兼容API

**开箱即用**：内置所有API地址和默认模型，零配置

**轻量零依赖**：核心框架不依赖任何Web框架，完全独立

**高性能**：全异步架构 + 连接池 + 自动重试

**MIT开源免费**：完全免费，可商用

## 支持哪些AI模型？

| 模型 | Provider名称 | 说明 |
|------|-------------|------|
| Ollama | `ollama` | 本地运行，免费 |
| OpenAI GPT | `openai` | 国际主流 |
| DeepSeek | `deepseek` | 性价比高，免费额度 |
| 通义千问 | `qwen` | 阿里云出品 |
| 智谱GLM | `glm` | 国产优秀 |
| 百度文心 | `baidu` | 中文理解强 |
| 腾讯混元 | `tencent` | 多模态支持 |
| 豆包 | `doubao` | 字节跳动 |
| Kimi | `kimi` | 长文本处理 |
| MiniMax | `minimax` | 多场景 |
| Claude | `claude` | Anthropic出品 |
| Gemini | `gemini` | Google出品 |
| 自定义 | `openai-compatible` | 任意OpenAI兼容API |

## 快速开始

### 安装

```bash
pip install thinkai-framework
```

### 3行代码开始使用

```python
from thinkai import ThinkAI

ai = ThinkAI(provider="ollama", model="llama3")
response = await ai.chat("你好，世界")
print(response.content)
```

## 丰富功能示例

### 多模型自由切换

```python
from thinkai import ThinkAI

ai = ThinkAI(provider="openai", api_key="your-key")

# 注册多个模型
ai.register_model("deepseek", provider="deepseek", api_key="your-key")
ai.register_model("qwen", provider="qwen", api_key="your-key")

# 自由切换
await ai.chat("你好", model="openai")
await ai.chat("你好", model="deepseek")
await ai.chat("你好", model="qwen")
```

### 流式响应

```python
ai = ThinkAI(provider="openai", api_key="your-key")

async for chunk in ai.chat_stream("讲一个故事"):
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### 会话管理（多轮对话）

```python
ai = ThinkAI()

async with ai.session() as session:
    response1 = await session.chat("你好,我想学习Python")
    response2 = await session.chat("有什么好的学习路径?")
    response3 = await session.chat("推荐一些资源吧")
```

### RAG（检索增强生成）

```python
from thinkai.rag import RAGPipeline

rag = RAGPipeline(
    documents=["./docs", "./knowledge"],
    ai_client=ai,
    chunk_size=500,
)

answer = await rag.query("ThinkAi框架支持哪些AI模型?")
```

### Agent（智能体）

```python
from thinkai.agent import ReActAgent, Tool

@Tool(name="calculator", description="计算数学表达式")
def calculator(expression: str) -> str:
    return str(eval(expression))

agent = ReActAgent(tools=[calculator], ai_client=ai)
result = await agent.run("计算25*48的结果")
```

### FastAPI集成

```python
from fastapi import FastAPI
from thinkai import ThinkAI

app = FastAPI()
ai = ThinkAI(provider="openai", api_key="your-key")

@app.post("/chat")
async def chat(message: str):
    response = await ai.chat(message)
    return {"content": response.content}

# 启动: uvicorn main:app --reload
```

## 技术架构

```
thinkai/
├── core/          # 核心模块 - 统一客户端
├── providers/     # 13个Provider - 开箱即用
├── session/       # 会话管理 - 多轮对话
├── rag/           # RAG - 检索增强生成
├── agent/         # Agent - 智能体
├── middleware/    # 中间件 - 日志/重试
├── prompt/        # Prompt模板
├── streaming.py   # 流式处理
└── exceptions.py  # 异常处理
```

## 为什么选择ThinkAi？

1. **开箱即用**：无需配置API地址，内置所有主流模型的默认配置
2. **一行切换**：`provider="模型名"` 即可在不同模型间切换
3. **轻量独立**：不绑定任何Web框架，可搭配Flask、Django、FastAPI等使用
4. **企业级**：异步架构、连接池、自动重试、中间件链
5. **完全免费**：MIT开源协议，可商用

## 相关链接

| 项目 | 地址 |
|------|------|
| PyPI | https://pypi.org/project/thinkai-framework/ |
| Gitee | https://gitee.com/hongxinge/think-ai |
| 版本 | v0.2.1 |
| 许可证 | MIT |

觉得好用的朋友别忘了给个Star！⭐
