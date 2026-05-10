"""工具定义"""
from typing import Callable, Optional, Dict, Any, List
import inspect
import json
from pydantic import BaseModel


class Tool:
    """
    工具类 - 封装可被Agent调用的函数
    
    使用示例:
        @tool
        def search(query: str) -> str:
            \"\"\"Search the web\"\"\"
            return "results"
        
        或手动创建:
        tool = Tool(
            name="calculator",
            description="Calculate math expressions",
            func=calculate,
            parameters={...}
        )
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters or self._infer_parameters(func)

    def _infer_parameters(self, func: Callable) -> Dict[str, Any]:
        """从函数签名推断参数schema"""
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == list:
                param_type = "array"
            
            properties[name] = {
                "type": param_type,
                "description": f"Parameter {name}",
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        if inspect.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        return self.func(**kwargs)

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __repr__(self) -> str:
        return f"Tool(name='{self.name}', description='{self.description}')"


def tool(name: Optional[str] = None, description: Optional[str] = None):
    """
    工具装饰器
    
    使用示例:
        @tool
        def search(query: str) -> str:
            \"\"\"Search the web\"\"\"
            ...
        
        @tool(name="calc", description="Calculate")
        def calculate(expr: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip()
        
        return Tool(
            name=tool_name,
            description=tool_desc,
            func=func,
        )
    
    return decorator
