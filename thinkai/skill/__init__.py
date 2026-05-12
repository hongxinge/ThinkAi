"""Skill系统 - 可复用的AI能力包"""
from typing import List, Dict, Any, Optional, Callable
import inspect

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
        # 内置Skill
        from thinkai.skill import WebSearchSkill, CodeSkill

        agent = FunctionCallingAgent(
            ai_client=ai,
            tools=[WebSearchSkill().get_tools()],
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
        """返回此Skill包含的工具列表"""
        return []

    def get_agent(self, ai_client: Optional[ThinkAI] = None) -> FunctionCallingAgent:
        """创建使用此Skill的Agent"""
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


class CodeSkill(Skill):
    """代码执行Skill"""

    name = "code"
    description = "Write and execute Python code"

    def get_tools(self) -> List[Tool]:
        def execute_python(code: str) -> str:
            """Execute Python code and return the output.

            Args:
                code: The Python code to execute
            """
            try:
                local_vars = {}
                exec(code, {}, local_vars)
                return str(local_vars.get("result", "Code executed successfully"))
            except Exception as e:
                return f"Error: {str(e)}"

        return [
            Tool(
                name="execute_python",
                description="Execute Python code and return the output",
                func=execute_python,
            ),
        ]


class MathSkill(Skill):
    """数学计算Skill"""

    name = "math"
    description = "Perform mathematical calculations"

    def get_tools(self) -> List[Tool]:
        def calculate(expression: str) -> str:
            """Calculate a mathematical expression.

            Args:
                expression: The math expression to evaluate
            """
            try:
                allowed_chars = set("0123456789+-*/.() ")
                if not all(c in allowed_chars for c in expression):
                    return "Error: Invalid characters in expression"
                result = eval(expression)
                return str(result)
            except Exception as e:
                return f"Error: {str(e)}"

        return [
            Tool(
                name="calculate",
                description="Calculate a mathematical expression",
                func=calculate,
            ),
        ]


class FileSkill(Skill):
    """文件操作Skill"""

    name = "file"
    description = "Read and write files"

    def get_tools(self) -> List[Tool]:
        def read_file(file_path: str) -> str:
            """Read the contents of a file.

            Args:
                file_path: Path to the file to read
            """
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error: {str(e)}"

        def write_file(file_path: str, content: str) -> str:
            """Write content to a file.

            Args:
                file_path: Path to the file to write
                content: The content to write
            """
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"File written successfully: {file_path}"
            except Exception as e:
                return f"Error: {str(e)}"

        return [
            Tool(
                name="read_file",
                description="Read the contents of a file",
                func=read_file,
            ),
            Tool(
                name="write_file",
                description="Write content to a file",
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
        """注册一个Skill"""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        """获取一个Skill"""
        return self._skills.get(name)

    def list_skills(self) -> List[Skill]:
        """列出所有已注册的Skill"""
        return list(self._skills.values())

    def get_all_tools(self) -> List[Tool]:
        """获取所有Skill的工具"""
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
