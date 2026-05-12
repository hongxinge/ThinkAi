"""Function Calling Agent - 使用原生OpenAI/Claude函数调用"""
from typing import Optional, List, Dict, Any, Callable
import json

from thinkai.core.client import ThinkAI
from thinkai.core.models import ChatMessage, ChatResponse, ToolCall, FunctionCall
from thinkai.agent.base import Agent
from thinkai.agent.tool import Tool


class FunctionCallingAgent(Agent):
    """
    Function Calling Agent - 使用原生函数调用能力

    工作流程:
    1. 将工具注册为 OpenAI 兼容格式
    2. 发送请求时携带 tools 参数
    3. 解析响应中的 tool_calls
    4. 执行工具并将结果返回给模型
    5. 直到模型返回最终答案
    """

    def __init__(
        self,
        name: str = "function-calling-agent",
        model: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 10,
        verbose: bool = False,
        ai_client: Optional[ThinkAI] = None,
        system_prompt: Optional[str] = None,
    ):
        super().__init__(
            name=name,
            model=model,
            tools=tools,
            max_iterations=max_iterations,
            verbose=verbose,
            ai_client=ai_client,
        )
        self.system_prompt = system_prompt or "You are a helpful assistant that can use tools to complete tasks."

    def _build_tools_spec(self) -> List[Dict[str, Any]]:
        """构建OpenAI兼容的工具规范"""
        return [tool.to_openai_format() for tool in self.tools]

    async def _execute_tool_call(self, tool_call: ToolCall) -> str:
        """执行单个工具调用"""
        func_name = tool_call.function.name
        try:
            func_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            func_args = {"input": tool_call.function.arguments}

        tool = self.get_tool(func_name)
        if not tool:
            return json.dumps({"error": f"Tool '{func_name}' not found"})

        try:
            if isinstance(func_args, dict):
                result = await tool.execute(**func_args)
            else:
                result = await tool.execute(input=func_args)
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def run(self, task: str, **kwargs) -> str:
        """
        运行Function Calling Agent

        Args:
            task: 任务描述
            **kwargs: 额外参数

        Returns:
            最终结果
        """
        if not self.ai_client:
            raise ValueError("ai_client is required for FunctionCallingAgent")

        messages = [
            ChatMessage.system(self.system_prompt),
            ChatMessage.user(task),
        ]

        tools_spec = self._build_tools_spec()
        has_tools = len(tools_spec) > 0

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            self._log(f"Iteration {iteration}")

            # 获取LLM响应
            if has_tools:
                response = await self.ai_client.chat(
                    messages=messages,
                    model=self.model,
                    tools=tools_spec,
                )
            else:
                response = await self.ai_client.chat(
                    messages=messages,
                    model=self.model,
                )

            assistant_msg = response.message
            messages.append(assistant_msg)

            # 检查是否有工具调用
            if assistant_msg.tool_calls:
                self._log(f"Tool calls: {len(assistant_msg.tool_calls)}")

                for tool_call in assistant_msg.tool_calls:
                    tool_name = tool_call.function.name
                    self._log(f"Executing: {tool_name}({tool_call.function.arguments})")

                    # 执行工具
                    result = await self._execute_tool_call(tool_call)
                    self._log(f"Result: {result}")

                    # 添加工具结果到消息列表
                    messages.append(ChatMessage(
                        role="tool",
                        content=result,
                        tool_call_id=tool_call.id,
                    ))
            else:
                # 没有工具调用,直接返回答案
                final_answer = assistant_msg.content or ""
                self._log(f"Final Answer: {final_answer}")
                return final_answer

        return "Error: Max iterations reached"

    async def chat_with_tools(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Tool]] = None,
    ) -> ChatResponse:
        """
        直接使用工具进行对话(不进入循环)

        Args:
            messages: 消息列表
            tools: 额外工具列表

        Returns:
            响应
        """
        all_tools = self._build_tools_spec()
        if tools:
            for tool in tools:
                all_tools.append(tool.to_openai_format())

        return await self.ai_client.chat(
            messages=messages,
            model=self.model,
            tools=all_tools,
        )
