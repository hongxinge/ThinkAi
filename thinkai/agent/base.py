"""Agent基类"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Any
from pydantic import BaseModel, Field

from thinkai.core.client import ThinkAI
from thinkai.core.models import ChatMessage
from thinkai.agent.tool import Tool


class AgentConfig(BaseModel):
    """Agent配置"""
    name: str = Field(default="agent", description="Agent名称")
    max_iterations: int = Field(default=10, description="最大迭代次数")
    max_execution_time: int = Field(default=300, description="最大执行时间(秒)")
    verbose: bool = Field(default=False, description="是否输出详细日志")


class Agent(ABC):
    """
    Agent基类
    """

    def __init__(
        self,
        name: str = "agent",
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
        **kwargs,
    ):
        self.name = name
        self.model = model
        self.tools = tools or []
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.ai_client = ai_client
        self.extra = kwargs

        self.on_start = on_start
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_finish = on_finish
        self.on_error = on_error

        self._tool_registry: Dict[str, Tool] = {}
        for tool in self.tools:
            self._tool_registry[tool.name] = tool

    @abstractmethod
    async def run(self, task: str, **kwargs) -> str:
        """
        运行Agent
        
        Args:
            task: 任务描述
            **kwargs: 额外参数
            
        Returns:
            执行结果
        """
        pass

    def add_tool(self, tool: Tool):
        """添加工具"""
        self._tool_registry[tool.name] = tool
        self.tools.append(tool)

    def remove_tool(self, tool_name: str):
        """移除工具"""
        if tool_name in self._tool_registry:
            del self._tool_registry[tool_name]
            self.tools = [t for t in self.tools if t.name != tool_name]

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tool_registry.get(tool_name)

    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tool_registry.values())

    def _log(self, message: str):
        """日志输出"""
        if self.verbose:
            print(f"[{self.name}] {message}")

    def _emit_hook(self, name: str, *args):
        """安全调用生命周期钩子"""
        hook = getattr(self, name, None)
        if hook is not None:
            try:
                hook(*args)
            except Exception:
                pass
