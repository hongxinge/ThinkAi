"""v0.4.0 新功能测试 - Memory, Multi-Agent, Streaming FC, 更多 Skills"""
import pytest
import asyncio
import json
import tempfile
import os
from pathlib import Path


def run_async(coro):
    """Python 3.13 compatible async runner"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class TestStreamingFunctionCallingAgent:
    """流式 Function Calling Agent 测试"""

    def test_import(self):
        from thinkai.agent import StreamingFunctionCallingAgent, StreamingFunctionCallResult
        assert StreamingFunctionCallingAgent is not None
        assert StreamingFunctionCallResult is not None

    def test_import_from_thinkai(self):
        from thinkai import StreamingFunctionCallingAgent, StreamingFunctionCallResult
        assert StreamingFunctionCallingAgent is not None
        assert StreamingFunctionCallResult is not None

    def test_create_streaming_agent(self):
        from thinkai import StreamingFunctionCallingAgent
        from thinkai.skill import MathSkill

        agent = StreamingFunctionCallingAgent(
            name="streaming-test",
            tools=MathSkill().get_tools(),
        )
        assert agent.name == "streaming-test"
        assert len(agent.tools) == 1

    def test_run_streaming_blocking(self):
        from thinkai import StreamingFunctionCallingAgent
        from thinkai.skill import MathSkill

        agent = StreamingFunctionCallingAgent(
            tools=MathSkill().get_tools(),
        )
        assert hasattr(agent, "run")
        assert hasattr(agent, "run_stream")

    def test_streaming_result_accumulation(self):
        from thinkai import StreamingFunctionCallResult

        result = StreamingFunctionCallResult()
        result.add_content("Hello")
        result.add_content(" ")
        result.add_content("World")

        assert result.content == "Hello World"

    def test_streaming_result_tool_calls(self):
        from thinkai import StreamingFunctionCallResult

        result = StreamingFunctionCallResult()
        result.tool_calls = [{"name": "calculate", "arguments": {"expression": "1+1"}}]
        result.tool_results = [{"name": "calculate", "result": "2"}]

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "calculate"


class TestMemorySystem:
    """记忆系统测试"""

    def test_import(self):
        from thinkai.memory import MemoryManager, MemoryItem, MemoryStore, FileMemoryStore
        assert MemoryManager is not None
        assert MemoryItem is not None

    def test_import_from_thinkai(self):
        from thinkai import MemoryManager, MemoryItem, MemoryStore, FileMemoryStore
        assert MemoryManager is not None

    def test_memory_item_creation(self):
        from thinkai import MemoryItem

        item = MemoryItem(
            content="Python is a programming language",
            memory_type="fact",
            importance=0.8,
            tags=["programming", "python"],
        )
        assert item.content == "Python is a programming language"
        assert item.memory_type == "fact"
        assert item.importance == 0.8
        assert "programming" in item.tags

    def test_memory_item_to_dict(self):
        from thinkai import MemoryItem

        item = MemoryItem(content="Test", importance=0.5)
        data = item.to_dict()

        assert "content" in data
        assert "timestamp" in data
        assert data["importance"] == 0.5

    def test_memory_item_from_dict(self):
        from thinkai import MemoryItem
        from datetime import datetime

        data = {
            "content": "Restored memory",
            "memory_type": "fact",
            "importance": 0.7,
            "timestamp": datetime.now().isoformat(),
            "source": "test",
            "tags": [],
            "access_count": 0,
            "last_accessed": datetime.now().isoformat(),
        }
        item = MemoryItem.from_dict(data)
        assert item.content == "Restored memory"
        assert item.importance == 0.7

    def test_file_memory_store(self):
        from thinkai import MemoryItem, FileMemoryStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(base_path=tmpdir)
            run_async(store.clear())

    def test_memory_manager_creation(self):
        from thinkai import MemoryManager

        manager = MemoryManager(max_memories=50)
        assert manager.max_memories == 50

    def test_memory_manager_remember_and_recall(self):
        from thinkai import MemoryManager, FileMemoryStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(base_path=tmpdir)
            manager = MemoryManager(store=store)

            async def test():
                await store.clear()
                await manager.remember("Python is great for AI", memory_type="fact", importance=0.9)
                await manager.remember("I prefer async programming", memory_type="preference", importance=0.7)

                results = await manager.recall("Python")
                assert len(results) > 0
                assert any("Python" in m.content for m in results)

            run_async(test())

    def test_memory_manager_build_context(self):
        from thinkai import MemoryManager, FileMemoryStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(base_path=tmpdir)
            manager = MemoryManager(store=store)

            async def test():
                await store.clear()
                await manager.remember("ThinkAi supports OpenAI", memory_type="fact", importance=0.8)
                context = await manager.build_context_prompt("OpenAI")
                assert "ThinkAi" in context or "OpenAI" in context

            run_async(test())

    def test_memory_stats(self):
        from thinkai import MemoryManager, FileMemoryStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(base_path=tmpdir)
            manager = MemoryManager(store=store)

            async def test():
                await store.clear()
                await manager.remember("Fact 1", memory_type="fact", importance=0.5)
                await manager.remember("Preference 1", memory_type="preference", importance=0.6)

                stats = await manager.get_stats()
                assert stats["total"] >= 2
                assert "fact" in stats["by_type"]

            run_async(test())


class TestMultiAgentOrchestrator:
    """多 Agent 协作测试"""

    def test_import(self):
        from thinkai.agent import MultiAgentOrchestrator, AgentRole, Task, TaskStatus
        assert MultiAgentOrchestrator is not None
        assert AgentRole is not None

    def test_import_from_thinkai(self):
        from thinkai import MultiAgentOrchestrator, AgentRole, Task, TaskStatus
        assert MultiAgentOrchestrator is not None
        assert AgentRole is not None
        assert Task is not None
        assert TaskStatus is not None

    def test_create_orchestrator(self):
        from thinkai import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator()
        assert orchestrator is not None
        assert len(orchestrator.agents) == 0

    def test_add_agent(self):
        from thinkai import MultiAgentOrchestrator, AgentRole
        from thinkai.skill import MathSkill
        from thinkai.agent import FunctionCallingAgent

        orchestrator = MultiAgentOrchestrator()
        agent = FunctionCallingAgent(name="math-agent", tools=MathSkill().get_tools())
        name = orchestrator.add_agent(
            agent=agent,
            role=AgentRole.SPECIALIST,
            capabilities=["math", "calculation"],
        )
        assert name == "math-agent"
        assert "math-agent" in orchestrator.agents

    def test_get_available_agents(self):
        from thinkai import MultiAgentOrchestrator, AgentRole
        from thinkai.skill import MathSkill, CodeSkill
        from thinkai.agent import FunctionCallingAgent

        orchestrator = MultiAgentOrchestrator()
        orchestrator.add_agent(
            FunctionCallingAgent(name="math", tools=MathSkill().get_tools()),
            capabilities=["math"],
        )
        orchestrator.add_agent(
            FunctionCallingAgent(name="code", tools=CodeSkill().get_tools()),
            capabilities=["coding"],
        )

        available = orchestrator.get_available_agents()
        assert len(available) == 2

        math_agents = orchestrator.get_available_agents(capability="math")
        assert len(math_agents) == 1
        assert "math" in math_agents

    def test_task_creation(self):
        from thinkai import Task, TaskStatus

        task = Task(task_id="test-1", description="Calculate 2+2")
        assert task.task_id == "test-1"
        assert task.status == TaskStatus.PENDING
        assert task.result is None

    def test_orchestrator_status(self):
        from thinkai import MultiAgentOrchestrator, AgentRole
        from thinkai.skill import MathSkill
        from thinkai.agent import FunctionCallingAgent

        orchestrator = MultiAgentOrchestrator()
        orchestrator.add_agent(
            FunctionCallingAgent(name="worker", tools=MathSkill().get_tools()),
            role=AgentRole.WORKER,
            capabilities=["math"],
        )

        status = orchestrator.get_status()
        assert "agents" in status
        assert "worker" in status["agents"]
        assert status["agents"]["worker"]["available"] == True

    def test_sequential_mode(self):
        from thinkai import MultiAgentOrchestrator
        from thinkai.skill import MathSkill
        from thinkai.agent import FunctionCallingAgent

        orchestrator = MultiAgentOrchestrator()
        orchestrator.add_agent(
            FunctionCallingAgent(name="agent1", tools=MathSkill().get_tools()),
        )

        status = orchestrator.get_status()
        assert len(status["agents"]) == 1


class TestAdditionalSkills:
    """更多 Skill 测试"""

    def test_database_skill(self):
        from thinkai.skill.builtin_skills import DatabaseSkill

        skill = DatabaseSkill()
        assert skill.name == "database"
        tools = skill.get_tools()
        assert len(tools) >= 3
        tool_names = [t.name for t in tools]
        assert "execute_sql" in tool_names
        assert "create_table" in tool_names
        assert "list_tables" in tool_names

    def test_api_skill(self):
        from thinkai.skill.builtin_skills import APISkill

        skill = APISkill()
        assert skill.name == "api"
        tools = skill.get_tools()
        assert len(tools) >= 2
        tool_names = [t.name for t in tools]
        assert "http_request" in tool_names
        assert "http_get" in tool_names

    def test_image_skill(self):
        from thinkai.skill.builtin_skills import ImageSkill

        skill = ImageSkill()
        assert skill.name == "image"
        tools = skill.get_tools()
        assert len(tools) >= 2
        tool_names = [t.name for t in tools]
        assert "image_info" in tool_names
        assert "list_images" in tool_names

    def test_text_skill(self):
        from thinkai.skill.builtin_skills import TextSkill

        skill = TextSkill()
        assert skill.name == "text"
        tools = skill.get_tools()
        assert len(tools) >= 2
        tool_names = [t.name for t in tools]
        assert "count_words" in tool_names
        assert "extract_keywords" in tool_names

    def test_text_skill_count_words(self):
        from thinkai.skill.builtin_skills import TextSkill

        skill = TextSkill()
        tools = skill.get_tools()
        count_tool = next(t for t in tools if t.name == "count_words")

        async def test():
            result = await count_tool.execute(text="Hello world, this is a test.")
            data = json.loads(result)
            assert data["words"] == 6
            assert data["characters"] > 6

        run_async(test())

    def test_text_skill_extract_keywords(self):
        from thinkai.skill.builtin_skills import TextSkill

        skill = TextSkill()
        tools = skill.get_tools()
        kw_tool = next(t for t in tools if t.name == "extract_keywords")

        async def test():
            text = "Python is a great programming language. Python is used in AI. Python programming is fun."
            result = await kw_tool.execute(text=text, top_n=3)
            data = json.loads(result)
            assert "keywords" in data
            assert len(data["keywords"]) > 0

        run_async(test())

    def test_system_skill(self):
        from thinkai.skill.builtin_skills import SystemSkill

        skill = SystemSkill()
        assert skill.name == "system"
        tools = skill.get_tools()
        assert len(tools) >= 2
        tool_names = [t.name for t in tools]
        assert "list_directory" in tool_names
        assert "get_system_info" in tool_names

    def test_database_skill_execute_sql(self):
        from thinkai.skill.builtin_skills import DatabaseSkill
        import tempfile

        skill = DatabaseSkill()
        tools = skill.get_tools()
        sql_tool = next(t for t in tools if t.name == "execute_sql")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            async def test():
                await sql_tool.execute(query=f"CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)", db_path=db_path)
                await sql_tool.execute(query="INSERT INTO test (name) VALUES ('Alice')", db_path=db_path)
                result = await sql_tool.execute(query="SELECT * FROM test", db_path=db_path)
                data = json.loads(result)
                assert data["count"] == 1
                assert "rows" in data

            run_async(test())


class TestGlobalSkillManager:
    """全局 SkillManager 包含所有新 Skill"""

    def test_all_builtin_skills_registered(self):
        from thinkai import skill_manager

        skill_names = [s.name for s in skill_manager.list_skills()]

        assert "web_search" in skill_names
        assert "code" in skill_names
        assert "math" in skill_names
        assert "file" in skill_names
        assert "database" in skill_names
        assert "api" in skill_names
        assert "image" in skill_names
        assert "text" in skill_names
        assert "system" in skill_names

    def test_all_tools_available(self):
        from thinkai import skill_manager

        all_tools = skill_manager.get_all_tools()
        tool_names = [t.name for t in all_tools]

        assert "calculate" in tool_names
        assert "execute_python" in tool_names
        assert "read_file" in tool_names
        assert "execute_sql" in tool_names
        assert "http_get" in tool_names
        assert "count_words" in tool_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
