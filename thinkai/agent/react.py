"""ReAct Agent - 推理+行动循环"""
from typing import Callable, Dict, Optional, List, Any
import json
import re
from thinkai.core.client import ThinkAI
from thinkai.core.models import ChatMessage
from thinkai.agent.base import Agent
from thinkai.agent.tool import Tool


class ReActAgent(Agent):
    """
    ReAct Agent - 推理(Reasoning)和行动(Acting)交替执行
    
    工作流程:
    1. 接收任务
    2. 思考下一步行动
    3. 调用工具(如果需要)
    4. 观察结果
    5. 重复2-4直到完成任务
    """

    def __init__(
        self,
        name: str = "react-agent",
        model: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 10,
        verbose: bool = False,
        ai_client: Optional[ThinkAI] = None,
        on_start: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[str, Dict], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
        on_finish: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        super().__init__(
            name=name,
            model=model,
            tools=tools,
            max_iterations=max_iterations,
            verbose=verbose,
            ai_client=ai_client,
            on_start=on_start,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
            on_finish=on_finish,
            on_error=on_error,
        )

    async def run(self, task: str, **kwargs) -> str:
        """
        运行ReAct Agent
        
        Args:
            task: 任务描述
            **kwargs: 额外参数
            
        Returns:
            最终结果
        """
        if not self.ai_client:
            raise ValueError("ai_client is required for ReActAgent")

        self._emit_hook("on_start", task)

        try:
            return await self._run_loop(task)
        except Exception as e:
            self._emit_hook("on_error", e)
            raise

    async def _run_loop(self, task: str) -> str:
        tools_desc = self._format_tools()

        system_prompt = f"""You are a helpful AI assistant that can use tools to complete tasks.

Available tools:
{tools_desc}

When you need to use a tool, respond with:
Thought: [your reasoning]
Action: [tool_name]
Action Input: [tool input as JSON]

After getting the tool result:
Observation: [tool result]

When you have enough information to answer:
Thought: [your reasoning]
Final Answer: [your final answer]

Remember to think step by step and use tools when needed."""

        messages = [
            ChatMessage.system(system_prompt),
            ChatMessage.user(task),
        ]

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            self._log(f"Iteration {iteration}")

            response = await self.ai_client.chat(
                messages=messages,
                model=self.model,
            )

            content = response.content or ""
            messages.append(ChatMessage.assistant(content))

            self._log(f"Response: {content}")

            if "Final Answer:" in content:
                final_answer = content.split("Final Answer:")[-1].strip()
                self._log(f"Final Answer: {final_answer}")
                self._emit_hook("on_finish", final_answer)
                return final_answer

            action_match = re.search(r"Action:\s*(\w+)", content)
            action_input_match = re.search(r"Action Input:\s*(.+)", content, re.DOTALL)

            if action_match and action_input_match:
                tool_name = action_match.group(1)
                try:
                    tool_input = json.loads(action_input_match.group(1).strip())
                except json.JSONDecodeError:
                    tool_input = {"input": action_input_match.group(1).strip()}

                self._log(f"Calling tool: {tool_name} with {tool_input}")

                self._emit_hook("on_tool_call", tool_name, tool_input)

                tool = self.get_tool(tool_name)
                if not tool:
                    observation = f"Error: Tool '{tool_name}' not found"
                else:
                    try:
                        result = await tool.execute(**tool_input)
                        observation = str(result)
                    except Exception as e:
                        observation = f"Error: {str(e)}"

                self._emit_hook("on_tool_result", tool_name, observation)
                self._log(f"Observation: {observation}")

                messages.append(ChatMessage.user(f"Observation: {observation}"))
            else:
                self._emit_hook("on_finish", content)
                return content

        self._emit_hook("on_finish", "Error: Max iterations reached")
        return "Error: Max iterations reached"

    def _format_tools(self) -> str:
        """格式化工具描述"""
        if not self.tools:
            return "No tools available"
        
        tools_str = []
        for tool in self.tools:
            tools_str.append(f"- {tool.name}: {tool.description}")
        
        return "\n".join(tools_str)
