"""ReAct Agent - 推理+行动循环"""
from typing import Optional, List, Dict, Any
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
    ):
        super().__init__(
            name=name,
            model=model,
            tools=tools,
            max_iterations=max_iterations,
            verbose=verbose,
            ai_client=ai_client,
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
        
        # 构建工具描述
        tools_desc = self._format_tools()
        
        # 构建系统提示
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
            
            # 获取LLM响应
            response = await self.ai_client.chat(
                messages=messages,
                model=self.model,
            )
            
            content = response.content or ""
            messages.append(ChatMessage.assistant(content))
            
            self._log(f"Response: {content}")
            
            # 检查是否有Final Answer
            if "Final Answer:" in content:
                final_answer = content.split("Final Answer:")[-1].strip()
                self._log(f"Final Answer: {final_answer}")
                return final_answer
            
            # 解析Action
            action_match = re.search(r"Action:\s*(\w+)", content)
            action_input_match = re.search(r"Action Input:\s*(.+)", content, re.DOTALL)
            
            if action_match and action_input_match:
                tool_name = action_match.group(1)
                try:
                    tool_input = json.loads(action_input_match.group(1).strip())
                except json.JSONDecodeError:
                    tool_input = {"input": action_input_match.group(1).strip()}
                
                self._log(f"Calling tool: {tool_name} with {tool_input}")
                
                # 执行工具
                tool = self.get_tool(tool_name)
                if not tool:
                    observation = f"Error: Tool '{tool_name}' not found"
                else:
                    try:
                        result = await tool.execute(**tool_input)
                        observation = str(result)
                    except Exception as e:
                        observation = f"Error: {str(e)}"
                
                self._log(f"Observation: {observation}")
                
                messages.append(ChatMessage.user(f"Observation: {observation}"))
            else:
                # 没有Action,直接返回
                return content
        
        return "Error: Max iterations reached"

    def _format_tools(self) -> str:
        """格式化工具描述"""
        if not self.tools:
            return "No tools available"
        
        tools_str = []
        for tool in self.tools:
            tools_str.append(f"- {tool.name}: {tool.description}")
        
        return "\n".join(tools_str)
