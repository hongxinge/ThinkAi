"""
ThinkAi 示例 - 基础使用
"""
import asyncio
from thinkai import ThinkAI


async def example_basic():
    """基础聊天示例"""
    print("=" * 50)
    print("示例1: 基础聊天")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    response = await ai.chat("你好,请介绍一下自己")
    print(f"回复: {response.content}")


async def example_multiple_models():
    """多模型切换示例"""
    print("\n" + "=" * 50)
    print("示例2: 多模型切换")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    ai.register_model(
        name="qwen",
        provider="qwen",
        model="qwen-turbo",
    )
    
    ai.register_model(
        name="deepseek",
        provider="deepseek",
        model="deepseek-chat",
    )
    
    print("可用模型:")
    print(ai.list_models())
    
    response = await ai.chat("你好", model="llama3")
    print(f"llama3回复: {response.content}")
    
    response = await ai.chat("你好", model="qwen")
    print(f"qwen回复: {response.content}")


async def example_session():
    """会话示例"""
    print("\n" + "=" * 50)
    print("示例3: 多轮对话")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    async with ai.session() as session:
        response1 = await session.chat("你好,我想学习Python")
        print(f"第一轮: {response1.content}")
        
        response2 = await session.chat("有什么好的学习路径?")
        print(f"第二轮: {response2.content}")
        
        response3 = await session.chat("推荐一些资源吧")
        print(f"第三轮: {response3.content}")


async def example_complete():
    """简化调用示例"""
    print("\n" + "=" * 50)
    print("示例4: 简化调用")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    content = await ai.complete("用Python写一个快速排序算法")
    print(content)


async def example_streaming():
    """流式响应示例"""
    print("\n" + "=" * 50)
    print("示例5: 流式响应")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    print("流式输出: ", end="", flush=True)
    async for chunk in ai.chat_stream("讲一个简短的笑话"):
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()


async def main():
    """运行所有示例"""
    await example_basic()
    await example_multiple_models()
    await example_session()
    await example_complete()
    await example_streaming()


if __name__ == "__main__":
    asyncio.run(main())
