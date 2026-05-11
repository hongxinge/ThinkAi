# ThinkAi 推广文案

---

## 一、宣传标题

### 主标题
**一行代码调用13个AI大模型！**

### 副标题
别再手动配置每个AI模型了！ThinkAi像用requests一样简单，开箱即用，MIT开源免费！

---

## 二、完整推广文案

### 🚀 引言

你是否曾经被AI大模型的接入折磨过？

- OpenAI配置一遍，再配DeepSeek，又配通义千问...
- 每个API格式都不一样，请求参数、响应解析全要重写
- 想换个模型？改代码改到怀疑人生！

现在，**ThinkAi** 帮你终结这一切！

### ✨ 什么是ThinkAi？

ThinkAi 是一个基于Python异步的企业级AI大模型集成框架，让你**一行代码就能调用13个主流AI大模型**。

```python
from thinkai import ThinkAI

# 一行代码，接入任何模型
ai = ThinkAI(provider="openai", api_key="your-key")
response = await ai.chat("你好")
print(response.content)
```

就是这么简单！

### 🎯 核心优势

| 优势 | 说明 |
|------|------|
| **一行代码接入** | `provider="模型名"` 即可使用，无需重复配置 |
| **13个主流模型** | OpenAI、DeepSeek、通义千问、GLM、百度文心、腾讯混元、豆包、Kimi、MiniMax、Claude、Gemini、Ollama... |
| **开箱即用** | 内置所有API地址和默认模型，零配置 |
| **轻量零依赖** | 核心框架不依赖任何Web框架，完全独立 |
| **高性能** | 全异步架构 + 连接池 + 自动重试 |
| **MIT开源免费** | 完全免费，可商用 |

### 📦 支持的AI模型

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

### 🎁 丰富功能

| 功能 | 代码行数 | 说明 |
|------|---------|------|
| 基础对话 | 3行 | 快速开始 |
| 多模型切换 | 5行 | 一个客户端切换多个模型 |
| 流式响应 | 5行 | SSE流式输出 |
| 会话管理 | 5行 | 多轮对话上下文 |
| RAG | 3行 | 检索增强生成 |
| Agent | 10行 | ReAct智能体 |

### 💻 快速开始

```bash
# 安装
pip install thinkai-framework
```

```python
# 3行代码开始使用
from thinkai import ThinkAI

ai = ThinkAI(provider="ollama", model="llama3")
response = await ai.chat("你好，世界")
print(response.content)
```

### 🌟 更多示例

#### 多模型自由切换

```python
ai = ThinkAI(provider="openai", api_key="your-key")

# 注册多个模型
ai.register_model("deepseek", provider="deepseek", api_key="your-key")
ai.register_model("qwen", provider="qwen", api_key="your-key")

# 自由切换
await ai.chat("你好", model="openai")
await ai.chat("你好", model="deepseek")
await ai.chat("你好", model="qwen")
```

#### 流式响应

```python
ai = ThinkAI(provider="openai", api_key="your-key")

async for chunk in ai.chat_stream("讲一个故事"):
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

#### FastAPI集成

```python
from fastapi import FastAPI
from thinkai import ThinkAI

app = FastAPI()
ai = ThinkAI(provider="openai", api_key="your-key")

@app.post("/chat")
async def chat(message: str):
    response = await ai.chat(message)
    return {"content": response.content}
```

### 📊 技术架构

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

### 🔗 相关链接

| 项目 | 地址 |
|------|------|
| PyPI | https://pypi.org/project/thinkai-framework/ |
| Gitee | https://gitee.com/hongxinge/think-ai |
| 版本 | v0.2.1 |
| 许可证 | MIT |

---

## 三、社交媒体短文案

### 微博/朋友圈版

```
🤖 一行代码调用13个AI大模型！

别再手动配置每个AI了！ThinkAi框架让你像用requests一样简单调用：
✅ OpenAI GPT
✅ DeepSeek
✅ 通义千问
✅ GLM
✅ 百度文心
✅ 腾讯混元
✅ 豆包
✅ Kimi
✅ MiniMax
✅ Claude
✅ Gemini
✅ Ollama
✅ 任意OpenAI兼容API

pip install thinkai-framework

MIT开源，完全免费！
🔗 https://pypi.org/project/thinkai-framework/
🔗 https://gitee.com/hongxinge/think-ai

#Python #AI #大模型 #OpenAI #开源
```

### 掘金/知乎版

**标题：一行代码调用13个AI大模型，这个Python框架太香了！**

**正文：**

还在手动配置每个AI模型的API？请求格式不同、响应解析不同、切换模型改代码改到崩溃？

今天我给大家分享一个开源项目：**ThinkAi**

一个基于Python异步的企业级AI大模型集成框架，让你一行代码就能调用13个主流AI大模型。

**安装只需一行命令：**
```bash
pip install thinkai-framework
```

**使用只需3行代码：**
```python
from thinkai import ThinkAI

ai = ThinkAI(provider="openai", api_key="your-key")
response = await ai.chat("你好")
print(response.content)
```

**支持13个模型：**
Ollama、OpenAI、DeepSeek、通义千问、GLM、百度文心、腾讯混元、豆包、Kimi、MiniMax、Claude、Gemini

**为什么选择ThinkAi？**
- 开箱即用：内置所有API地址和默认模型
- 一行切换：`provider="模型名"` 即可切换
- 轻量零依赖：不绑定任何Web框架
- 高性能：全异步架构
- MIT开源：完全免费，可商用

**GitHub/Gitee地址：**
https://gitee.com/hongxinge/think-ai

**PyPI地址：**
https://pypi.org/project/thinkai-framework/

觉得好用的朋友别忘了给个Star！⭐

---

## 四、宣传海报文案

### 海报主标题
**一行代码调用13个AI大模型**

### 海报副标题
ThinkAi - 像用requests一样简单

### 海报要点
1. 🎯 一行代码接入
2. 🌐 13个主流模型
3. ⚡ 开箱即用
4. 🆓 MIT开源免费

### 海报底部
MIT 开源协议 · 免费商用 · pypi.org/project/thinkai-framework · gitee.com/hongxinge/think-ai
