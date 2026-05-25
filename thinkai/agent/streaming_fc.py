"""流式 Function Calling Agent - 支持流式响应中的工具调用"""
from typing import Optional, List, Dict, Any, AsyncIterator, Callable
import json

from thinkai.core.client import ThinkAI
from thinkai.core.models import ChatMessage, ChatResponse, ToolCall, FunctionCall, StreamChunk
from thinkai.agent.base import Agent
from thinkai.agent.tool import Tool


class StreamingFunctionCallResult:
    """流式 Function Calling 结果"""

    def __init__(self):
        self.content_chunks: List[str] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.tool_results: List[Dict[str, Any]] = []
        self.is_final_answer = False

    @property
    def content(self) -> str:
        return "".join(self.content_chunks)

    def add_content(self, chunk: str):
        self.content_chunks.append(chunk)


class StreamingFunctionCallingAgent(Agent):
    """
    流式 Function Calling Agent - 支持流式响应和工具调用

    工作流程:
    1. 流式输出模型响应
    2. 检测 tool_calls
    3. 执行工具
    4. 继续流式输出直到最终答案

    使用示例:
        agent = StreamingFunctionCallingAgent(
            ai_client=ai,
            tools=[MathSkill().get_tools()],
        )

        async for result in agent.run_stream("计算123*456"):
            if result.tool_calls:
                print("调用工具:", result.tool_calls)
            elif result.content:
                print(result.content, end="", flush=True)
    """

    def __init__(
        self,
        name: str = "streaming-fc-agent",
        model: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 10,
        verbose: bool = False,
        ai_client: Optional[ThinkAI] = None,
        system_prompt: Optional[str] = None,
        on_tool_start: Optional[Callable[[str, Dict], None]] = None,
        on_tool_end: Optional[Callable[[str, str], None]] = None,
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
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end

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

    @staticmethod
    def _merge_tool_calls(
        accumulated: List[ToolCall],
        delta_calls: Optional[List[ToolCall]],
    ) -> List[ToolCall]:
        """合并流式增量 tool_calls 到累积列表"""
        if not delta_calls:
            return accumulated

        for delta_tc in delta_calls:
            idx = None
            if delta_tc.id:
                for i, existing in enumerate(accumulated):
                    if existing.id == delta_tc.id:
                        idx = i
                        break

            if idx is not None:
                existing = accumulated[idx]
                if delta_tc.function.name:
                    existing.function.name += delta_tc.function.name
                if delta_tc.function.arguments:
                    existing.function.arguments += delta_tc.function.arguments
            else:
                accumulated.append(ToolCall(
                    id=delta_tc.id or "",
                    type=delta_tc.type,
                    function=FunctionCall(
                        name=delta_tc.function.name or "",
                        arguments=delta_tc.function.arguments or "",
                    ),
                ))

        return accumulated

    async def run_stream(
        self,
        task: str,
        **kwargs,
    ) -> AsyncIterator[StreamingFunctionCallResult]:
        """
        流式运行Function Calling Agent

        使用 chat_stream 实现真正的流式输出:
        - 最终答案: 逐 chunk 实时 yield
        - 工具调用: 累积完整 tool_calls 后执行, yield 工具结果, 继续循环

        Args:
            task: 任务描述
            **kwargs: 额外参数

        Yields:
            StreamingFunctionCallResult: 流式结果
        """
        if not self.ai_client:
            raise ValueError("ai_client is required for StreamingFunctionCallingAgent")

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

            request_params: Dict[str, Any] = {
                "messages": messages,
                "model": self.model,
            }
            if has_tools:
                request_params["tools"] = tools_spec

            accumulated_content = ""
            accumulated_tool_calls: List[ToolCall] = []
            has_tool_calls = False

            stream = self.ai_client.chat_stream(**request_params)

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    accumulated_content += delta.content

                if delta.tool_calls:
                    has_tool_calls = True
                    accumulated_tool_calls = self._merge_tool_calls(
                        accumulated_tool_calls, delta.tool_calls
                    )

                if not has_tool_calls and delta.content:
                    result = StreamingFunctionCallResult()
                    result.add_content(delta.content)
                    result.is_final_answer = False
                    yield result

                finish = choice.finish_reason
                if finish in ("stop", "tool_calls"):
                    break

            if has_tool_calls:
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=accumulated_content or None,
                    tool_calls=accumulated_tool_calls,
                )
                messages.append(assistant_msg)

                self._log(f"Tool calls: {len(accumulated_tool_calls)}")

                for tool_call in accumulated_tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {"input": tool_call.function.arguments}

                    if self.on_tool_start:
                        self.on_tool_start(tool_name, func_args)

                    self._log(f"Executing: {tool_name}({tool_call.function.arguments})")

                    result_str = await self._execute_tool_call(tool_call)
                    self._log(f"Result: {result_str}")

                    if self.on_tool_end:
                        self.on_tool_end(tool_name, result_str)

                    messages.append(ChatMessage(
                        role="tool",
                        content=result_str,
                        tool_call_id=tool_call.id,
                    ))

                    tool_result = StreamingFunctionCallResult()
                    tool_result.tool_calls = [{
                        "name": tool_name,
                        "arguments": func_args,
                    }]
                    tool_result.tool_results = [{
                        "name": tool_name,
                        "result": result_str,
                    }]
                    yield tool_result
            else:
                self._log(f"Final Answer: {accumulated_content}")

                final_result = StreamingFunctionCallResult()
                final_result.is_final_answer = True
                yield final_result
                return

        result = StreamingFunctionCallResult()
        result.content_chunks = ["Error: Max iterations reached"]
        result.is_final_answer = True
        yield result

    async def run(
        self,
        task: str,
        on_chunk: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> str:
        """
        运行Function Calling Agent (阻塞版本,内部使用流式)

        Args:
            task: 任务描述
            on_chunk: 每个内容块的回调函数
            **kwargs: 额外参数

        Returns:
            最终结果
        """
        all_content = []

        async for result in self.run_stream(task, **kwargs):
            if result.content:
                all_content.append(result.content)
                if on_chunk:
                    on_chunk(result.content)
            if result.tool_calls:
                for tc in result.tool_calls:
                    self._log(f"Tool: {tc['name']}")

        return "".join(all_content)
