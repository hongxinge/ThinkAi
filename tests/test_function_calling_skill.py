"""Function Calling 和 Skill 系统测试"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestFunctionCallingAgent:
    """Function Calling Agent 测试"""

    def test_import(self):
        """测试导入"""
        from thinkai.agent import FunctionCallingAgent
        assert FunctionCallingAgent is not None

    def test_import_from_thinkai(self):
        """测试从 thinkai 导入"""
        from thinkai import FunctionCallingAgent
        assert FunctionCallingAgent is not None

    def test_create_agent(self):
        """测试创建 Agent"""
        from thinkai.agent import FunctionCallingAgent
        from thinkai.skill import MathSkill

        agent = FunctionCallingAgent(
            name="test-agent",
            tools=MathSkill().get_tools(),
            verbose=False,
        )
        assert agent.name == "test-agent"
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "calculate"

    def test_agent_has_ai_client(self):
        """测试 Agent 带有 ai_client"""
        from thinkai.agent import FunctionCallingAgent
        from thinkai.skill import MathSkill
        from thinkai import ThinkAI

        ai = ThinkAI(provider="ollama", model="llama3")
        agent = FunctionCallingAgent(
            ai_client=ai,
            tools=MathSkill().get_tools(),
        )
        assert agent.ai_client is ai

    def test_build_tools_spec(self):
        """测试构建工具规范"""
        from thinkai.agent import FunctionCallingAgent
        from thinkai.skill import MathSkill

        agent = FunctionCallingAgent(tools=MathSkill().get_tools())
        tools_spec = agent._build_tools_spec()
        
        assert len(tools_spec) == 1
        assert tools_spec[0]["type"] == "function"
        assert tools_spec[0]["function"]["name"] == "calculate"
        assert "description" in tools_spec[0]["function"]
        assert "parameters" in tools_spec[0]["function"]


class TestSkillSystem:
    """Skill 系统测试"""

    def test_import_skills(self):
        """测试导入 Skills"""
        from thinkai.skill import Skill, SkillManager
        from thinkai.skill import WebSearchSkill, CodeSkill, MathSkill, FileSkill
        
        assert Skill is not None
        assert SkillManager is not None
        assert WebSearchSkill is not None
        assert CodeSkill is not None
        assert MathSkill is not None
        assert FileSkill is not None

    def test_import_from_thinkai(self):
        """测试从 thinkai 导入"""
        from thinkai import Skill, SkillManager, skill_manager
        from thinkai import WebSearchSkill, CodeSkill, MathSkill, FileSkill
        
        assert Skill is not None
        assert SkillManager is not None
        assert skill_manager is not None

    def test_web_search_skill(self):
        """测试 WebSearchSkill"""
        from thinkai.skill import WebSearchSkill

        skill = WebSearchSkill()
        assert skill.name == "web_search"
        tools = skill.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "web_search"

    def test_code_skill(self):
        """测试 CodeSkill"""
        from thinkai.skill import CodeSkill

        skill = CodeSkill()
        assert skill.name == "code"
        tools = skill.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "execute_python"

    def test_code_skill_execute(self):
        """测试 CodeSkill 执行代码"""
        from thinkai.skill import CodeSkill
        import asyncio

        skill = CodeSkill()
        tools = skill.get_tools()
        
        async def test_execute():
            result = await tools[0].execute(code="result = 2 + 3")
            return result

        result = asyncio.run(test_execute())
        assert "5" in result

    def test_math_skill(self):
        """测试 MathSkill"""
        from thinkai.skill import MathSkill

        skill = MathSkill()
        assert skill.name == "math"
        tools = skill.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "calculate"

    def test_math_skill_calculate(self):
        """测试 MathSkill 计算"""
        from thinkai.skill import MathSkill
        import asyncio

        skill = MathSkill()
        tools = skill.get_tools()
        
        async def test_calculate():
            result = await tools[0].execute(expression="2 + 3 * 4")
            return result

        result = asyncio.run(test_calculate())
        assert result == "14"

    def test_file_skill(self):
        """测试 FileSkill"""
        from thinkai.skill import FileSkill

        skill = FileSkill()
        assert skill.name == "file"
        tools = skill.get_tools()
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names

    def test_skill_manager(self):
        """测试 SkillManager"""
        from thinkai.skill import SkillManager, MathSkill

        manager = SkillManager()
        manager.register(MathSkill())
        
        skills = manager.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "math"

        skill = manager.get("math")
        assert skill is not None
        assert skill.name == "math"

    def test_skill_manager_get_all_tools(self):
        """测试 SkillManager 获取所有工具"""
        from thinkai.skill import SkillManager, MathSkill, CodeSkill

        manager = SkillManager()
        manager.register(MathSkill())
        manager.register(CodeSkill())
        
        all_tools = manager.get_all_tools()
        assert len(all_tools) == 2
        tool_names = [t.name for t in all_tools]
        assert "calculate" in tool_names
        assert "execute_python" in tool_names

    def test_global_skill_manager(self):
        """测试全局 skill_manager 预注册"""
        from thinkai.skill import skill_manager

        skills = skill_manager.list_skills()
        skill_names = [s.name for s in skills]
        
        assert "web_search" in skill_names
        assert "code" in skill_names
        assert "math" in skill_names
        assert "file" in skill_names

    def test_skill_get_agent(self):
        """测试 Skill 创建 Agent"""
        from thinkai.skill import MathSkill
        from thinkai.agent import FunctionCallingAgent

        skill = MathSkill()
        agent = skill.get_agent()
        
        assert isinstance(agent, FunctionCallingAgent)
        assert agent.name == "math-agent"


class TestToolOpenAIFormat:
    """工具 OpenAI 格式转换测试"""

    def test_tool_to_openai_format(self):
        """测试工具转 OpenAI 格式"""
        from thinkai.agent import Tool

        def dummy_tool_func(x: int, y: str) -> str:
            """Dummy tool"""
            return y * x

        tool = Tool(
            name="dummy",
            description="Dummy tool",
            func=dummy_tool_func,
        )
        
        spec = tool.to_openai_format()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "dummy"
        assert spec["function"]["description"] == "Dummy tool"
        assert "parameters" in spec["function"]

    def test_tool_parameters_inference(self):
        """测试参数推断"""
        from thinkai.agent import Tool

        def calc(a: int, b: float, c: str) -> str:
            return c

        tool = Tool(name="calc", description="calc", func=calc)
        params = tool.parameters
        
        assert params["properties"]["a"]["type"] == "integer"
        assert params["properties"]["b"]["type"] == "number"
        assert params["properties"]["c"]["type"] == "string"


class TestToolCallsParsing:
    """Tool Calls 解析测试"""

    def test_parse_response_with_tool_calls(self):
        """测试解析带 tool_calls 的响应"""
        from thinkai.providers.base import BaseProvider
        from thinkai.core.models import ToolCall, FunctionCall, ChatMessage

        response_data = {
            "id": "test-123",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "calculate",
                                    "arguments": '{"expression": "2+3"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        class MockProvider(BaseProvider):
            name = "mock"
            default_model = "mock-model"
            default_api_base = "http://mock.com"
            
            async def chat(self, request):
                pass
            
            async def chat_stream(self, request):
                pass

        provider = MockProvider()
        parsed = provider._parse_response(response_data)
        
        assert parsed.id == "test-123"
        assert len(parsed.choices) == 1
        assert parsed.choices[0].message.tool_calls is not None
        assert len(parsed.choices[0].message.tool_calls) == 1
        assert parsed.choices[0].message.tool_calls[0].function.name == "calculate"


class TestModelDefinitions:
    """模型定义测试"""

    def test_tool_call_model(self):
        """测试 ToolCall 模型"""
        from thinkai.core.models import ToolCall, FunctionCall

        tc = ToolCall(
            id="call_123",
            type="function",
            function=FunctionCall(
                name="search",
                arguments='{"query": "test"}',
            ),
        )
        
        assert tc.id == "call_123"
        assert tc.function.name == "search"

    def test_chat_message_with_tool_calls(self):
        """测试带 tool_calls 的 ChatMessage"""
        from thinkai.core.models import ChatMessage, ToolCall, FunctionCall, MessageRole

        tc = ToolCall(
            id="call_123",
            function=FunctionCall(name="calc", arguments='{"expr": "1+1"}'),
        )
        
        msg = ChatMessage.assistant(content=None, tool_calls=[tc])
        
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content is None
        assert len(msg.tool_calls) == 1

    def test_chat_request_with_tools(self):
        """测试带 tools 的 ChatRequest"""
        from thinkai.core.models import ChatRequest, ChatMessage, Tool, FunctionDefinition

        tool = Tool(
            type="function",
            function=FunctionDefinition(
                name="calculate",
                description="Calculate",
                parameters={"type": "object", "properties": {}},
            ),
        )
        
        request = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage.user("1+1=?")],
            tools=[tool],
        )
        
        assert request.tools is not None
        assert len(request.tools) == 1
        assert request.tools[0].function.name == "calculate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
