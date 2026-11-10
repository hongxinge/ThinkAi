"""
ThinkAi 示例 - Agent使用
"""
import ast
import asyncio
import operator

from thinkai import ThinkAI
from thinkai.agent import ReActAgent, tool


# 仅允许基础数学运算符，杜绝 eval() 注入
_MATH_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    """对 AST 节点做白名单求值，只允许数字常量与数学运算。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _MATH_OPS:
        return _MATH_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _MATH_OPS:
        return _MATH_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError("表达式包含不支持的语法")


@tool(name="calculator", description="Calculate mathematical expressions")
def calculator(expression: str) -> str:
    """计算数学表达式（AST 白名单求值，不使用 eval）。"""
    try:
        return str(_safe_eval(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"Error: {e}"


@tool(name="search", description="Search information from knowledge base")
async def search(query: str) -> str:
    """搜索知识库(模拟)"""
    knowledge = {
        "python": "Python是一种广泛使用的高级编程语言,以其代码可读性而闻名。",
        "fastapi": "FastAPI是一个现代、快速(高性能)的Web框架,用于构建API。",
        "thinkai": "ThinkAi是基于Python异步的企业级AI大模型集成框架,不依赖任何Web框架。",
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
