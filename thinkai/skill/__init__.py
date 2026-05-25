"""Skill系统 - 可复用的AI能力包"""
from typing import List, Dict, Any, Optional, Callable
import inspect
import ast
import operator
import os

from thinkai.agent.tool import Tool, tool
from thinkai.agent.function_calling import FunctionCallingAgent
from thinkai.core.client import ThinkAI
from thinkai.skill.builtin_skills import DatabaseSkill, APISkill, ImageSkill, TextSkill, SystemSkill


class Skill:
    """
    Skill - 可复用的AI能力包

    一个Skill包含一组工具,封装特定领域的AI能力。
    用户可以组合多个Skill来构建强大的Agent。

    使用示例:
        from thinkai.skill import WebSearchSkill, CodeSkill

        agent = FunctionCallingAgent(
            ai_client=ai,
            tools=WebSearchSkill().get_tools() + CodeSkill().get_tools(),
        )

        # 自定义Skill
        class MySkill(Skill):
            def get_tools(self):
                return [Tool(name="my_tool", ...)]
    """

    name: str = "base"
    description: str = "Base skill"

    def __init__(self, ai_client: Optional[ThinkAI] = None):
        self.ai_client = ai_client

    def get_tools(self) -> List[Tool]:
        return []

    def get_agent(self, ai_client: Optional[ThinkAI] = None) -> FunctionCallingAgent:
        client = ai_client or self.ai_client
        return FunctionCallingAgent(
            name=f"{self.name}-agent",
            tools=self.get_tools(),
            ai_client=client,
            system_prompt=self.description,
        )


class WebSearchSkill(Skill):
    """网页搜索Skill"""

    name = "web_search"
    description = "Search the web for information"

    def get_tools(self) -> List[Tool]:
        def search(query: str, num_results: int = 5) -> str:
            """Search the web and return relevant results.

            Args:
                query: The search query
                num_results: Number of results to return (default: 5)
            """
            return f"[Search results for '{query}'] (需要实现实际搜索API)"

        return [
            Tool(
                name="web_search",
                description="Search the web for information",
                func=search,
            ),
        ]


_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "int": int,
    "isinstance": isinstance, "len": len, "list": list, "map": map,
    "max": max, "min": min, "print": print, "range": range,
    "round": round, "set": set, "sorted": sorted, "str": str,
    "sum": sum, "tuple": tuple, "zip": zip,
}

_FORBIDDEN_NAMES = {
    "import", "importlib", "__import__", "exec", "eval", "compile",
    "open", "input", "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "hasattr", "type",
    "object", "classmethod", "staticmethod", "property",
    "super", "memoryview", "bytearray", "bytes",
    "exit", "quit", "help", "credits", "license",
    "breakpoint", "copyright",
}


class _SafeCodeValidator(ast.NodeVisitor):
    """AST验证器 - 检查代码是否包含危险操作"""

    def __init__(self):
        self.errors: List[str] = []

    def visit_Import(self, node):
        self.errors.append("import statements are not allowed")

    def visit_ImportFrom(self, node):
        self.errors.append("import statements are not allowed")

    def visit_Attribute(self, node):
        if isinstance(node.attr, str) and node.attr.startswith('_'):
            self.errors.append(f"accessing private attributes is not allowed: {node.attr}")
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in _FORBIDDEN_NAMES:
            self.errors.append(f"accessing '{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node):
        self.generic_visit(node)

    def visit_Global(self, node):
        self.errors.append("global statements are not allowed")

    def visit_Nonlocal(self, node):
        self.errors.append("nonlocal statements are not allowed")


class CodeSkill(Skill):
    """代码执行Skill - 安全沙箱执行"""

    name = "code"
    description = "Write and execute Python code in a safe sandbox"

    def __init__(self, allowed_dirs: Optional[List[str]] = None, max_output_length: int = 10000):
        self.allowed_dirs = allowed_dirs
        self.max_output_length = max_output_length

    def get_tools(self) -> List[Tool]:
        allowed_dirs = self.allowed_dirs
        max_output_length = self.max_output_length

        def execute_python(code: str) -> str:
            """Execute Python code in a safe sandbox and return the output.

            The code runs in a restricted environment:
            - No imports, file access, or system calls
            - Only safe builtins are available
            - Private attribute access is blocked

            The last expression's value is returned as the result.
            Use 'result = ...' to set the output explicitly.

            Args:
                code: The Python code to execute (must be safe, no imports or file access)
            """
            try:
                tree = ast.parse(code)
                validator = _SafeCodeValidator()
                validator.visit(tree)
                if validator.errors:
                    return f"SafetyError: {validator.errors[0]}. Imports, file access, and system calls are not allowed in sandbox mode."

                safe_globals = {"__builtins__": _SAFE_BUILTINS}
                local_vars = {}

                compiled = compile(tree, "<sandbox>", "exec")
                exec(compiled, safe_globals, local_vars)

                result = local_vars.get("result", local_vars.get("_", "Code executed successfully"))
                result_str = str(result)
                if len(result_str) > max_output_length:
                    result_str = result_str[:max_output_length] + "...(truncated)"
                return result_str
            except SyntaxError as e:
                return f"SyntaxError: {e}"
            except Exception as e:
                return f"Error: {type(e).__name__}: {e}"

        return [
            Tool(
                name="execute_python",
                description="Execute Python code in a safe sandbox (no imports, file access, or system calls)",
                func=execute_python,
            ),
        ]


_MATH_OPERATORS = {
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


def _safe_math_eval(expr: str) -> float:
    """安全的数学表达式求值 - 使用AST解析,只允许数学运算"""
    tree = ast.parse(expr, mode='eval')

    def _eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.UnaryOp):
            op_func = _MATH_OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op_func(_eval_node(node.operand))
        elif isinstance(node, ast.BinOp):
            op_func = _MATH_OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op_func(_eval_node(node.left), _eval_node(node.right))
        else:
            raise ValueError(f"Unsupported expression: {type(node).__name__}")

    return _eval_node(tree.body)


class MathSkill(Skill):
    """数学计算Skill - 安全AST解析"""

    name = "math"
    description = "Perform mathematical calculations safely"

    def get_tools(self) -> List[Tool]:
        def calculate(expression: str) -> str:
            """Calculate a mathematical expression safely.

            Supports: +, -, *, /, //, %, ** and numeric constants.
            No variables, function calls, or imports are allowed.

            Args:
                expression: The math expression to evaluate (e.g., "2**10 + 3*5")
            """
            try:
                result = _safe_math_eval(expression)
                return str(result)
            except ValueError as e:
                return f"Error: {e}"
            except SyntaxError:
                return "Error: Invalid expression syntax"
            except Exception as e:
                return f"Error: {type(e).__name__}: {e}"

        return [
            Tool(
                name="calculate",
                description="Calculate a mathematical expression (supports +, -, *, /, //, %, **)",
                func=calculate,
            ),
        ]


class FileSkill(Skill):
    """文件操作Skill - 支持路径安全限制"""

    name = "file"
    description = "Read and write files within allowed directories"

    def __init__(self, allowed_dirs: Optional[List[str]] = None):
        self.allowed_dirs = [os.path.abspath(d) for d in (allowed_dirs or ["."])]

    def _is_path_allowed(self, file_path: str) -> bool:
        abs_path = os.path.abspath(file_path)
        return any(abs_path.startswith(d) for d in self.allowed_dirs)

    def get_tools(self) -> List[Tool]:
        allowed_dirs = self.allowed_dirs

        def read_file(file_path: str) -> str:
            """Read the contents of a file within allowed directories.

            Args:
                file_path: Path to the file to read (must be within allowed directories)
            """
            try:
                abs_path = os.path.abspath(file_path)
                if not any(abs_path.startswith(d) for d in allowed_dirs):
                    return f"Error: Access denied. Path '{file_path}' is outside allowed directories."
                with open(abs_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error: {e}"

        def write_file(file_path: str, content: str) -> str:
            """Write content to a file within allowed directories.

            Args:
                file_path: Path to the file to write (must be within allowed directories)
                content: The content to write
            """
            try:
                abs_path = os.path.abspath(file_path)
                if not any(abs_path.startswith(d) for d in allowed_dirs):
                    return f"Error: Access denied. Path '{file_path}' is outside allowed directories."
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"File written successfully: {file_path}"
            except Exception as e:
                return f"Error: {e}"

        return [
            Tool(
                name="read_file",
                description="Read the contents of a file (restricted to allowed directories)",
                func=read_file,
            ),
            Tool(
                name="write_file",
                description="Write content to a file (restricted to allowed directories)",
                func=write_file,
            ),
        ]


class SkillManager:
    """
    Skill管理器 - 注册和管理Skill
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self) -> List[Skill]:
        return list(self._skills.values())

    def get_all_tools(self) -> List[Tool]:
        all_tools = []
        for skill in self._skills.values():
            all_tools.extend(skill.get_tools())
        return all_tools

    def create_agent(
        self,
        ai_client: ThinkAI,
        skill_names: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> FunctionCallingAgent:
        """
        创建Agent,自动组合指定Skill的工具

        Args:
            ai_client: ThinkAI客户端
            skill_names: 要使用的Skill名称列表,None表示使用全部
            system_prompt: 系统提示

        Returns:
            FunctionCallingAgent实例
        """
        skills = []
        if skill_names:
            for name in skill_names:
                skill = self.get(name)
                if skill:
                    skills.append(skill)
        else:
            skills = self.list_skills()

        all_tools = []
        for skill in skills:
            all_tools.extend(skill.get_tools())

        description = " ".join([s.description for s in skills])
        prompt = system_prompt or f"You are a helpful assistant with the following capabilities: {description}"

        return FunctionCallingAgent(
            name="skill-agent",
            tools=all_tools,
            ai_client=ai_client,
            system_prompt=prompt,
        )


skill_manager = SkillManager()

skill_manager.register(WebSearchSkill())
skill_manager.register(CodeSkill())
skill_manager.register(MathSkill())
skill_manager.register(FileSkill())
skill_manager.register(DatabaseSkill())
skill_manager.register(APISkill())
skill_manager.register(ImageSkill())
skill_manager.register(TextSkill())
skill_manager.register(SystemSkill())
