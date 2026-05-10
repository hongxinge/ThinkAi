"""
ThinkAi 示例 - Agent使用
"""
import asyncio
from thinkai import ThinkAI
from thinkai.agent import ReActAgent, Tool


# 定义工具
@Tool(name="calculator", description="Calculate mathematical expressions")
def calculator(expression: str) -> str:
    """计算数学表达式"""
    try:
        # 安全计算
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"


@Tool(name="search", description="Search information from knowledge base")
async def search(query: str) -> str:
    """搜索知识库(模拟)"""
    knowledge = {
        "python": "Python是一种广泛使用的高级编程语言,以其代码可读性而闻名。",
        "fastapi": "FastAPI是一个现代、快速(高性能)的Web框架,用于构建API。",
        "thinkai": "ThinkAi是一个基于FastAPI的企业级AI框架,支持多种大模型集成。",
    }
    
    for key, value in knowledge.items():
        if key in query.lower():
            return value
    
    return "No relevant information found."


async def example_agent():
    """Agent示例"""
    print("=" * 50)
    print("示例: ReAct Agent")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    agent = ReActAgent(
        name="research-assistant",
        tools=[calculator, search],
        ai_client=ai,
        verbose=True,
    )
    
    # 运行任务
    task = "计算 25 * 48 的结果,然后搜索Python的相关信息"
    print(f"\n任务: {task}")
    
    result = await agent.run(task)
    print(f"\n最终结果: {result}")


async def example_agent_math():
    """Agent数学任务"""
    print("\n" + "=" * 50)
    print("示例: Agent数学计算")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    agent = ReActAgent(
        name="math-agent",
        tools=[calculator],
        ai_client=ai,
        verbose=True,
    )
    
    task = "计算 (123 + 456) * 789 的结果"
    print(f"\n任务: {task}")
    
    result = await agent.run(task)
    print(f"\n最终结果: {result}")


async def main():
    """运行示例"""
    await example_agent()
    await example_agent_math()


if __name__ == "__main__":
    asyncio.run(main())
