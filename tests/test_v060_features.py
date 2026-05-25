"""v0.6.0新增功能测试 - 缓存/结构化输出/速率限制/追踪/插件/状态持久化"""
import pytest
import asyncio
import json
import os
import tempfile
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class TestCache:
    def test_memory_cache_basic(self):
        cache = __import__("thinkai.cache", fromlist=["MemoryCache"]).MemoryCache(max_size=10, default_ttl=60)
        run_async(cache.set("key1", {"content": "hello"}))
        result = run_async(cache.get("key1"))
        assert result is not None
        assert result["content"] == "hello"

    def test_memory_cache_miss(self):
        cache = __import__("thinkai.cache", fromlist=["MemoryCache"]).MemoryCache()
        result = run_async(cache.get("nonexistent"))
        assert result is None

    def test_memory_cache_delete(self):
        cache = __import__("thinkai.cache", fromlist=["MemoryCache"]).MemoryCache()
        run_async(cache.set("key1", "value1"))
        run_async(cache.delete("key1"))
        result = run_async(cache.get("key1"))
        assert result is None

    def test_memory_cache_clear(self):
        cache = __import__("thinkai.cache", fromlist=["MemoryCache"]).MemoryCache()
        run_async(cache.set("k1", "v1"))
        run_async(cache.set("k2", "v2"))
        run_async(cache.clear())
        assert run_async(cache.get("k1")) is None
        assert run_async(cache.get("k2")) is None

    def test_memory_cache_lru_eviction(self):
        cache = __import__("thinkai.cache", fromlist=["MemoryCache"]).MemoryCache(max_size=3)
        run_async(cache.set("a", 1))
        run_async(cache.set("b", 2))
        run_async(cache.set("c", 3))
        run_async(cache.set("d", 4))
        assert run_async(cache.get("a")) is None
        assert run_async(cache.get("d")) == 4

    def test_memory_cache_ttl_expiry(self):
        cache = __import__("thinkai.cache", fromlist=["MemoryCache"]).MemoryCache(default_ttl=0)
        run_async(cache.set("key", "value", ttl=0))
        import time
        time.sleep(0.1)
        result = run_async(cache.get("key"))
        assert result is None

    def test_file_cache_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = __import__("thinkai.cache", fromlist=["FileCache"]).FileCache(cache_dir=tmpdir)
            run_async(cache.set("key1", {"data": "hello"}))
            result = run_async(cache.get("key1"))
            assert result is not None
            assert result["data"] == "hello"

    def test_file_cache_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = __import__("thinkai.cache", fromlist=["FileCache"]).FileCache(cache_dir=tmpdir)
            run_async(cache.set("key1", "value1"))
            run_async(cache.delete("key1"))
            result = run_async(cache.get("key1"))
            assert result is None

    def test_create_cache_factory(self):
        from thinkai.cache import create_cache
        mem_cache = create_cache("memory")
        assert mem_cache is not None
        file_cache = create_cache("file", cache_dir=tempfile.mkdtemp())
        assert file_cache is not None

    def test_cached_decorator(self):
        from thinkai.cache import cached
        call_count = 0

        @cached(ttl=60)
        async def expensive_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = run_async(expensive_func(5))
        result2 = run_async(expensive_func(5))
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    def test_cache_middleware(self):
        from thinkai.cache import CacheMiddleware
        from thinkai.core.models import ChatRequest
        mw = CacheMiddleware(ttl=60)
        req = ChatRequest(model="test", messages=[])
        result = run_async(mw.process_request(req))
        assert result is not None


class TestStructuredOutput:
    def test_generate_schema_prompt(self):
        from thinkai.structured import generate_schema_prompt

        class PersonInfo(BaseModel):
            name: str = Field(description="Person's name")
            age: int = Field(description="Person's age")

        prompt = generate_schema_prompt(PersonInfo)
        assert "name" in prompt
        assert "age" in prompt
        assert "JSON" in prompt

    def test_parse_json_response_raw(self):
        from thinkai.structured import parse_json_response
        result = parse_json_response('{"name": "Alice", "age": 30}')
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_parse_json_response_code_block(self):
        from thinkai.structured import parse_json_response
        result = parse_json_response('```json\n{"name": "Bob", "age": 25}\n```')
        assert result["name"] == "Bob"

    def test_parse_json_response_generic_block(self):
        from thinkai.structured import parse_json_response
        result = parse_json_response('```\n{"name": "Charlie", "age": 35}\n```')
        assert result["name"] == "Charlie"

    def test_validate_and_create(self):
        from thinkai.structured import validate_and_create

        class PersonInfo(BaseModel):
            name: str
            age: int

        person = validate_and_create(PersonInfo, {"name": "Alice", "age": 30})
        assert person.name == "Alice"
        assert person.age == 30

    def test_validate_and_create_error(self):
        from thinkai.structured import validate_and_create, StructuredOutputError
        from pydantic import ValidationError

        class PersonInfo(BaseModel):
            name: str
            age: int

        with pytest.raises((StructuredOutputError, ValidationError)):
            validate_and_create(PersonInfo, {"name": "Alice", "age": "not_a_number"})


class TestRateLimit:
    def test_token_bucket_basic(self):
        from thinkai.middleware.rate_limit import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=10, capacity=5)
        assert run_async(limiter.try_acquire(1)) is True

    def test_token_bucket_exhaust(self):
        from thinkai.middleware.rate_limit import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(rate=1, capacity=2)
        assert run_async(limiter.try_acquire(1)) is True
        assert run_async(limiter.try_acquire(1)) is True
        assert run_async(limiter.try_acquire(1)) is False

    def test_concurrent_limiter(self):
        from thinkai.middleware.rate_limit import ConcurrentLimiter

        async def test_concurrent():
            limiter = ConcurrentLimiter(max_concurrent=2)

            async def use_limiter():
                async with limiter:
                    await asyncio.sleep(0.01)

            await asyncio.gather(use_limiter(), use_limiter())

        asyncio.run(test_concurrent())

    def test_rate_limit_middleware(self):
        from thinkai.middleware.rate_limit import RateLimitMiddleware
        from thinkai.core.models import ChatRequest, ChatResponse
        mw = RateLimitMiddleware(requests_per_minute=60, max_concurrent=5)
        req = ChatRequest(model="test", messages=[])
        result = run_async(mw.process_request(req))
        assert result is not None
        resp = ChatResponse(id="test", model="test", choices=[])
        result = run_async(mw.process_response(resp))
        assert result is not None


class TestTracing:
    def test_trace_span_creation(self):
        from thinkai.tracing import TraceSpan
        span = TraceSpan(name="test_span")
        assert span.name == "test_span"
        assert span.status == "started"
        assert span.span_id is not None

    def test_trace_span_finish(self):
        from thinkai.tracing import TraceSpan
        span = TraceSpan(name="test_span")
        span.finish("completed")
        assert span.status == "completed"
        assert span.end_time is not None
        assert span.duration_ms is not None

    def test_trace_span_events(self):
        from thinkai.tracing import TraceSpan
        span = TraceSpan(name="test_span")
        span.add_event("tool_call", tool_name="calculate")
        assert len(span.events) == 1
        assert span.events[0]["name"] == "tool_call"

    def test_trace_span_attributes(self):
        from thinkai.tracing import TraceSpan
        span = TraceSpan(name="test_span")
        span.set_attribute("model", "gpt-4")
        assert span.attributes["model"] == "gpt-4"

    def test_tracer_start_span(self):
        from thinkai.tracing import Tracer
        tracer = Tracer()
        span = tracer.start_span("test_operation")
        assert span.name == "test_operation"
        tracer.finish_span(span)
        assert span.status == "completed"

    def test_tracer_context_manager(self):
        from thinkai.tracing import Tracer
        tracer = Tracer()

        async def use_trace():
            async with tracer.trace("test_op", model="gpt-4"):
                pass

        run_async(use_trace())

    def test_console_exporter(self):
        from thinkai.tracing import TraceSpan, ConsoleTraceExporter
        exporter = ConsoleTraceExporter()
        span = TraceSpan(name="test_span")
        span.finish("completed")
        exporter.export(span)

    def test_json_exporter(self):
        from thinkai.tracing import TraceSpan, JSONTraceExporter
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "traces.json")
            exporter = JSONTraceExporter(output_file=path)
            span = TraceSpan(name="test_span")
            span.finish("completed")
            exporter.export(span)
            assert os.path.exists(path)

    def test_get_tracer(self):
        from thinkai.tracing import get_tracer
        tracer = get_tracer()
        assert tracer is not None


class TestPlugin:
    def test_plugin_info_creation(self):
        from thinkai.plugin import PluginInfo
        info = PluginInfo(
            name="test-plugin",
            version="1.0",
            description="Test plugin",
            plugin_type="skill",
            entry_point="test_module:TestClass",
        )
        assert info.name == "test-plugin"
        assert info.plugin_type == "skill"

    def test_plugin_manager_register(self):
        from thinkai.plugin import PluginManager, PluginInfo
        mgr = PluginManager()
        info = PluginInfo(
            name="test-plugin",
            version="1.0",
            description="Test",
            plugin_type="skill",
            entry_point="test:Test",
        )
        mgr.register(info)
        plugins = mgr.list_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "test-plugin"

    def test_plugin_manager_is_loaded(self):
        from thinkai.plugin import PluginManager
        mgr = PluginManager()
        assert mgr.is_loaded("nonexistent") is False

    def test_thinkai_plugin_decorator(self):
        from thinkai.plugin import thinkai_plugin

        @thinkai_plugin(name="decorated-plugin", version="1.0", description="Test", plugin_type="skill")
        class TestSkill:
            pass

        assert hasattr(TestSkill, '_thinkai_plugin_info')
        assert TestSkill._thinkai_plugin_info.name == "decorated-plugin"


class TestAgentState:
    def test_agent_state_creation(self):
        from thinkai.agent.state import AgentState
        state = AgentState(
            agent_name="test-agent",
            agent_type="react",
            status="running",
            current_step=1,
            max_steps=10,
        )
        assert state.agent_name == "test-agent"
        assert state.status == "running"

    def test_agent_state_serialization(self):
        from thinkai.agent.state import AgentState
        state = AgentState(
            agent_name="test-agent",
            agent_type="react",
            status="running",
            current_step=1,
            max_steps=10,
        )
        json_str = state.to_json()
        restored = AgentState.from_json(json_str)
        assert restored.agent_name == "test-agent"
        assert restored.current_step == 1

    def test_memory_state_storage(self):
        from thinkai.agent.state import MemoryStateStorage, AgentState
        storage = MemoryStateStorage()
        state = AgentState(
            agent_name="test-agent",
            agent_type="react",
            status="running",
            current_step=1,
            max_steps=10,
        )
        state_id = run_async(storage.save(state))
        loaded = run_async(storage.load(state_id))
        assert loaded.agent_name == "test-agent"

    def test_memory_state_storage_list(self):
        from thinkai.agent.state import MemoryStateStorage, AgentState
        storage = MemoryStateStorage()
        state1 = AgentState(agent_name="agent-1", agent_type="react", status="completed", current_step=5, max_steps=10)
        state2 = AgentState(agent_name="agent-2", agent_type="react", status="running", current_step=3, max_steps=10)
        run_async(storage.save(state1))
        run_async(storage.save(state2))
        states = run_async(storage.list_states())
        assert len(states) == 2

    def test_memory_state_storage_delete(self):
        from thinkai.agent.state import MemoryStateStorage, AgentState
        storage = MemoryStateStorage()
        state = AgentState(agent_name="test", agent_type="react", status="running", current_step=1, max_steps=10)
        state_id = run_async(storage.save(state))
        run_async(storage.delete(state_id))
        states = run_async(storage.list_states())
        assert len(states) == 0

    def test_file_state_storage(self):
        from thinkai.agent.state import FileStateStorage, AgentState
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStateStorage(storage_dir=tmpdir)
            state = AgentState(agent_name="test", agent_type="react", status="running", current_step=1, max_steps=10)
            state_id = run_async(storage.save(state))
            loaded = run_async(storage.load(state_id))
            assert loaded.agent_name == "test"

    def test_create_state_storage_factory(self):
        from thinkai.agent.state import create_state_storage
        mem = create_state_storage("memory")
        assert mem is not None
        file = create_state_storage("file", storage_dir=tempfile.mkdtemp())
        assert file is not None


class TestToolDecorator:
    def test_tool_decorator_no_parens(self):
        from thinkai.agent.tool import tool

        @tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        assert isinstance(greet, object)
        assert hasattr(greet, 'name') or hasattr(greet, 'func')

    def test_tool_decorator_with_name(self):
        from thinkai.agent.tool import tool

        @tool(name="custom_name", description="Custom tool")
        def my_func(x: int) -> int:
            return x * 2

        assert isinstance(my_func, object)

    def test_tool_auto_parameters(self):
        from thinkai.agent.tool import Tool
        t = Tool(
            name="test",
            description="Test tool",
            func=lambda x, y=5: x + y,
        )
        params = t.parameters
        assert "properties" in params
        assert "x" in params["properties"]


class TestPromptTemplates:
    def test_chain_of_thought_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("chain_of_thought", question="Why is the sky blue?")
        assert "step by step" in result.lower()
        assert "sky" in result

    def test_few_shot_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("few_shot", examples="Q: 2+2? A: 4", question="Q: 3+3?")
        assert "examples" in result.lower() or "Q:" in result

    def test_summarize_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("summarize", text="Long text here")
        assert "summar" in result.lower()

    def test_translate_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("translate", source_lang="English", target_lang="Chinese", text="Hello")
        assert "English" in result
        assert "Chinese" in result

    def test_code_review_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("code_review", language="Python", code="print('hello')")
        assert "Python" in result
        assert "review" in result.lower()

    def test_data_extraction_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("data_extraction", fields="name, age", text="John is 30")
        assert "name" in result
        assert "JSON" in result

    def test_role_play_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("role_play", role="expert", role_description="a Python expert", message="How to learn Python?")
        assert "expert" in result

    def test_debate_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("debate", proposition="AI will replace programmers")
        assert "AI" in result

    def test_api_design_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("api_design", service_description="todo app")
        assert "todo" in result

    def test_test_generation_template(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("test_generation", language="Python", code="def add(a,b): return a+b")
        assert "Python" in result
