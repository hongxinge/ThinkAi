"""工具定义"""
from typing import Callable, Optional, Dict, Any, List, Union, get_origin, get_args
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

        或带参数装饰:
        @tool(name="calc", description="Calculate")
        def calculate(expr: str) -> str:
            ...

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

    @staticmethod
    def _python_type_to_json_schema(annotation: Any) -> Dict[str, Any]:
        """将Python类型注解转换为JSON Schema"""
        if annotation == inspect.Parameter.empty:
            return {"type": "string"}

        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is Union:
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                return Tool._python_type_to_json_schema(non_none_args[0])
            return {"type": "string"}

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        if annotation in type_map:
            return {"type": type_map[annotation]}

        if origin is list:
            schema: Dict[str, Any] = {"type": "array"}
            if args:
                schema["items"] = Tool._python_type_to_json_schema(args[0])
            return schema

        if origin is dict:
            schema = {"type": "object"}
            if args and len(args) >= 2:
                schema["additionalProperties"] = Tool._python_type_to_json_schema(args[1])
            return schema

        return {"type": "string"}

    def _infer_parameters(self, func: Callable) -> Dict[str, Any]:
        """从函数签名推断参数schema"""
        sig = inspect.signature(func)
        properties = {}
        required = []

        for pname, param in sig.parameters.items():
            schema = self._python_type_to_json_schema(param.annotation)
            schema["description"] = f"Parameter {pname}"

            if param.default != inspect.Parameter.empty:
                schema["default"] = param.default
            else:
                required.append(pname)

            properties[pname] = schema

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


def _tool_factory(
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Callable[[Callable], Tool]:
    """
    工具装饰器工厂（内部使用）

    当 @tool 带参数调用时使用此工厂:
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


def tool(
    _func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Any:
    """
    工具装饰器 - 支持两种用法

    用法1 - 直接装饰（无括号）:
        @tool
        def search(query: str) -> str:
            \"\"\"Search the web\"\"\"
            ...

    用法2 - 带参数装饰:
        @tool(name="calc", description="Calculate")
        def calculate(expr: str) -> str:
            ...
    """
    if _func is not None:
        return Tool(
            name=name or _func.__name__,
            description=description or (_func.__doc__ or "").strip(),
            func=_func,
        )

    return _tool_factory(name=name, description=description)
