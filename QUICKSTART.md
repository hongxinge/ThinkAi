# ThinkAi 快速开始指南

## 环境要求

- Python 3.9+ (你的版本: Python 3.13.13 ✓)
- 至少一个AI模型Provider (Ollama/OpenAI/通义千问/DeepSeek等)

## 第一步: 安装ThinkAi框架

### 方式1: 本地开发使用(推荐)

```bash
# 进入项目目录
cd G:\ThinkAi

# 安装框架(开发模式,可编辑)
pip install -e .

# 或安装所有依赖
pip install -e ".[all]"
```

### 方式2: 安装必要依赖

```bash
pip install fastapi uvicorn pydantic pydantic-settings httpx pyyaml python-dotenv tenacity
```

## 第二步: 配置AI模型

### 选项A: 使用Ollama(本地模型,免费)

1. 下载安装Ollama: https://ollama.com/download
2. 拉取模型:
   ```bash
   ollama pull llama3
   ```
3. Ollama会自动运行在 http://localhost:11434

### 选项B: 使用OpenAI(云端,需要API Key)

1. 注册OpenAI账号: https://platform.openai.com
2. 获取API Key
3. 创建 `.env` 文件:
   ```bash
   # 复制示例文件
   copy .env.example .env
   
   # 编辑.env文件,填入API Key
   OPENAI_API_KEY=sk-your-api-key-here
   ```

### 选项C: 使用通义千问(阿里云)

1. 注册阿里云账号
2. 开通DashScope服务
3. 获取API Key
4. 在 `.env` 中添加:
   ```
   QWEN_API_KEY=your-qwen-api-key
   ```

## 第三步: 运行示例

### 1. 基础聊天示例

```bash
cd G:\ThinkAi
python examples\basic_usage.py
```

### 2. 启动FastAPI服务(推荐)

**方式1: 双击启动**
```
双击 G:\ThinkAi\启动服务.bat
```

**方式2: 命令行启动**
```bash
cd G:\ThinkAi
python -m uvicorn examples.fastapi_demo:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后:
- API接口: http://localhost:8000
- API文档(可交互): http://localhost:8000/docs
- 自动重载: 修改代码后自动重启

### 3. 测试API

打开浏览器访问 http://localhost:8000/docs

点击 `/chat` 接口,输入:
```json
{
  "message": "你好,请介绍一下ThinkAi框架",
  "model": "llama3"
}
```

点击"Execute"执行,查看响应。

## 第四步: 创建你的第一个AI应用

### 示例1: 最简单的聊天机器人

创建文件 `my_chatbot.py`:

```python
from thinkai import ThinkAI
import asyncio

async def main():
    # 创建AI客户端
    ai = ThinkAI(provider="ollama", model="llama3")
    
    # 聊天
    response = await ai.chat("你好,请写一首关于AI的诗")
    print(response.content)

if __name__ == "__main__":
    asyncio.run(main())
```

运行:
```bash
python my_chatbot.py
```

### 示例2: 多轮对话机器人

```python
from thinkai import ThinkAI
import asyncio

async def main():
    ai = ThinkAI(provider="ollama", model="llama3")
    
    # 使用会话管理(自动保存上下文)
    async with ai.session() as session:
        while True:
            user_input = input("\n你: ")
            if user_input.lower() in ["退出", "exit", "quit"]:
                break
            
            response = await session.chat(user_input)
            print(f"AI: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例3: 集成到现有FastAPI项目

```python
from fastapi import FastAPI
from thinkai import ThinkAI

app = FastAPI()

# 创建全局AI实例
ai = ThinkAI(provider="ollama", model="llama3")

@app.post("/api/chat")
async def chat(message: str):
    """聊天接口"""
    response = await ai.chat(message)
    return {"reply": response.content}

@app.post("/api/complete")
async def complete(prompt: str):
    """文本生成接口"""
    content = await ai.complete(prompt)
    return {"text": content}

# 启动: uvicorn main:app --reload
```

## 常见问题

### Q1: 如何查看可用的Provider?

```python
from thinkai import ThinkAI

ai = ThinkAI()
print(ai.list_providers())
```

### Q2: 如何切换模型?

```python
# 方式1: 创建时指定
ai = ThinkAI(provider="openai", model="gpt-4")

# 方式2: 运行时切换
response = await ai.chat("你好", model="gpt-4")
```

### Q3: 如何配置多个模型?

```python
ai = ThinkAI(provider="ollama", model="llama3")

# 注册其他模型
ai.register_model("gpt4", provider="openai", model="gpt-4")
ai.register_model("qwen", provider="qwen", model="qwen-turbo")

# 使用不同模型
response1 = await ai.chat("你好", model="llama3")
response2 = await ai.chat("你好", model="gpt4")
response3 = await ai.chat("你好", model="qwen")
```

### Q4: 如何使用流式响应?

```python
ai = ThinkAI()

async for chunk in ai.chat_stream("讲一个故事"):
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Q5: 报错"Connection refused"怎么办?

检查Provider是否正常运行:
- Ollama: 确保 `ollama serve` 正在运行
- OpenAI: 检查API Key是否正确
- 网络: 检查是否能访问API地址

## 下一步

- 查看 [README.md](README.md) 了解完整功能
- 查看 [examples/](examples/) 目录中的示例代码
- 查看 [RELEASE_GUIDE.md](RELEASE_GUIDE.md) 了解如何发布到PyPI
- 访问文档: https://thinkai.readthedocs.io

## 获取帮助

- Issue: https://github.com/thinkai/thinkai/issues
- 文档: https://thinkai.readthedocs.io
