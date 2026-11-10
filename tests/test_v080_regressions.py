"""v0.8.0 回归测试：覆盖实证核验确认的缺陷。

设计约束：全部用例不依赖外部服务、不发起网络请求；
可选依赖缺失时由用例自身声明门禁，避免"看似通过"的假绿。
"""
import asyncio
import importlib
import inspect

import pytest


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _make_response(content="ok"):
    from thinkai.core.models import ChatResponse, ChatChoice, ChatMessage
    return ChatResponse(
        id="resp-1",
        model="test-model",
        choices=[ChatChoice(index=0, message=ChatMessage.assistant(content))],
    )


class TestCacheKeyRegression:
    """缓存键必须区分一切影响响应的请求参数，同时忽略框架内部标记。"""

    @staticmethod
    def _req(**kwargs):
        from thinkai.core.models import ChatRequest, ChatMessage
        return ChatRequest(
            model="m", messages=[ChatMessage.user("hi")], temperature=0.7, **kwargs
        )

    def test_tools_change_cache_key(self):
        from thinkai.cache import CacheMiddleware
        from thinkai.core.models import Tool, FunctionDefinition
        k = CacheMiddleware._make_cache_key
        tool = Tool(type="function", function=FunctionDefinition(name="f", parameters={}))
        assert k(self._req()) != k(self._req(tools=[tool]))

    def test_sampling_params_change_cache_key(self):
        from thinkai.cache import CacheMiddleware
        k = CacheMiddleware._make_cache_key
        assert k(self._req()) != k(self._req(max_tokens=128))
        assert k(self._req()) != k(self._req(top_p=0.1))

    def test_internal_markers_do_not_change_cache_key(self):
        from thinkai.cache import CacheMiddleware
        k = CacheMiddleware._make_cache_key
        req = self._req()
        req.extra["_cache_key"] = "internal"
        req.extra["_cache_hit"] = True
        assert k(req) == k(self._req())


class TestRetrySemanticsRegression:
    def test_rate_limit_error_exposes_retry_after(self):
        from thinkai.exceptions import RateLimitError
        assert RateLimitError("openai", 30).retry_after == 30

    def test_connection_error_is_retryable(self):
        from thinkai.exceptions import APIConnectionError
        from thinkai.middleware.retry_middleware import RetryMiddleware
        assert RetryMiddleware().is_retryable(APIConnectionError("boom", "p"))

    def test_retry_delay_prefers_upstream_retry_after(self, monkeypatch):
        """上游给出 Retry-After 时，客户端只等待一次且采用该值。"""
        import thinkai.core.client as client_mod
        from thinkai.core.client import ThinkAI
        from thinkai.exceptions import RateLimitError
        from thinkai.middleware.retry_middleware import RetryMiddleware

        delays = []

        async def fake_sleep(delay):
            delays.append(delay)

        monkeypatch.setattr(client_mod.asyncio, "sleep", fake_sleep)

        class FlakyProvider:
            def __init__(self):
                self.calls = 0

            async def chat(self, request):
                self.calls += 1
                if self.calls == 1:
                    raise RateLimitError("p", 30)
                return _make_response("ok")

            async def close(self):
                pass

        ai = ThinkAI(provider="ollama")
        ai.add_middleware(RetryMiddleware(max_retries=1, delay=1.0))
        ai._main_provider = FlakyProvider()
        assert run_async(ai.chat("hi")).content == "ok"
        assert delays == [30]


class TestSplitterRegression:
    def test_all_splitters_validate_overlap(self):
        from thinkai.rag.text_splitter import (
            CharacterSplitter, TokenSplitter, RecursiveSplitter,
        )
        for cls in (CharacterSplitter, TokenSplitter, RecursiveSplitter):
            splitter = cls(chunk_size=10, chunk_overlap=20)
            assert splitter.chunk_overlap < splitter.chunk_size, cls.__name__

    def test_empty_input_returns_no_chunks(self):
        from thinkai.rag.text_splitter import (
            CharacterSplitter, TokenSplitter, RecursiveSplitter,
        )
        for cls in (CharacterSplitter, TokenSplitter, RecursiveSplitter):
            assert cls().split("") == [], cls.__name__

    def test_recursive_respects_chunk_size_with_extreme_params(self):
        from thinkai.rag.text_splitter import RecursiveSplitter
        splitter = RecursiveSplitter(chunk_size=10, chunk_overlap=20)
        chunks = splitter.split("abcdefghij" * 4)
        assert chunks
        assert all(len(c) <= 10 for c in chunks)


class TestExampleAndMCPRegression:
    def test_agent_example_is_importable(self):
        mod = importlib.import_module("examples.agent_example")
        assert hasattr(mod, "calculator")
        assert hasattr(mod, "search")

    def test_mcp_wrapper_preserves_input_schema(self):
        from thinkai.mcp import MCPAdapter, MCPTool
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        adapter = MCPAdapter()
        mcp_tool = MCPTool("read_file", "读文件", schema)
        adapter._mcp_tools["fs"] = [mcp_tool]
        assert adapter._wrap_mcp_tool(mcp_tool).parameters == schema

    def test_chat_stream_exposes_tools_param(self):
        from thinkai.core.client import ThinkAI
        assert "tools" in inspect.signature(ThinkAI.chat_stream).parameters


class TestConfigRegression:
    def test_yaml_env_placeholder_is_expanded(self, monkeypatch, tmp_path):
        monkeypatch.setenv("THINKAI_TEST_KEY", "sk-test-123")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            'providers:\n  openai:\n    api_key: "${THINKAI_TEST_KEY}"\n',
            encoding="utf-8",
        )
        from thinkai.core.config import Settings
        settings = Settings.from_file(str(cfg))
        assert settings.providers["openai"].api_key == "sk-test-123"

    def test_provider_key_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        from thinkai.core.config import Settings
        assert Settings().get_provider_config("openai").api_key == "sk-from-env"


class TestRegistryRegression:
    """锁定设计：预设 Provider 统一由 OpenAI 兼容层提供服务。"""

    def test_preset_providers_resolve_to_compatible_layer(self):
        from thinkai.providers.registry import registry
        for name in ("openai", "qwen", "deepseek", "glm"):
            cls = registry.get(name)
            assert cls is not None
            assert cls.__module__ == "thinkai.providers.shortcuts", (name, cls.__module__)


class TestRAGUsabilityRegression:
    def test_pipeline_constructs_without_optional_deps(self):
        from thinkai.rag import RAGPipeline
        assert RAGPipeline().indexed is False

    def test_default_vector_store_is_zero_dependency(self):
        from thinkai.rag import RAGPipeline
        from thinkai.rag.vector_store import InMemoryVectorStore
        assert isinstance(RAGPipeline().vector_store, InMemoryVectorStore)

    def test_in_memory_store_is_exported(self):
        from thinkai.rag import InMemoryVectorStore
        assert InMemoryVectorStore is not None

    def test_redis_storage_is_exported(self):
        from thinkai.session import RedisStorage
        assert RedisStorage is not None

    def test_retrieve_reuses_existing_vector_store(self):
        """新实例应能检索已有向量库，不应因 self.indexed=False 短路。"""
        from thinkai.rag import RAGPipeline
        pipeline = RAGPipeline()

        async def _run():
            vector = await pipeline.embedding.embed_text("hello")
            await pipeline.vector_store.add_documents(
                texts=["hello"], embeddings=[vector], metadatas=[{"source": "x"}]
            )
            return await pipeline.retrieve("hello", top_k=1)

        assert run_async(_run()), "已有向量应可被新实例检索"

    def test_add_document_appends_metadata(self, tmp_path):
        from thinkai.rag import RAGPipeline
        first = tmp_path / "a.txt"
        second = tmp_path / "b.txt"
        first.write_text("第一段内容", encoding="utf-8")
        second.write_text("第二段内容", encoding="utf-8")
        pipeline = RAGPipeline(documents=[str(first)])
        run_async(pipeline.index())
        initial = len(pipeline._chunk_metadata)
        run_async(pipeline.add_document(str(second)))
        assert len(pipeline._chunk_metadata) > initial

    def test_embedding_provider_param_is_respected(self):
        from thinkai import ThinkAI
        from thinkai.rag import RAGPipeline
        from thinkai.rag.embedding import SimpleHashEmbedding
        ai = ThinkAI(provider="ollama")
        assert isinstance(
            RAGPipeline(ai_client=ai, embedding_provider="simple").embedding,
            SimpleHashEmbedding,
        )

    def test_switch_provider_accepts_credentials(self):
        from thinkai import ThinkAI
        assert "api_key" in inspect.signature(ThinkAI.switch_provider).parameters


class TestOrchestratorRegression:
    """多 Agent 编排的执行统计与并发上限必须真实生效。"""

    def test_failed_task_does_not_count_as_success(self):
        from thinkai.agent.orchestrator import AgentNode, Task

        class FailingAgent:
            name = "failing"

            async def run(self, task, **kwargs):
                raise RuntimeError("boom")

        node = AgentNode(FailingAgent())
        result = run_async(node.execute_task(Task(task_id="t1", description="x")))
        assert result.startswith("Error:")
        assert node.task_count == 1
        assert node.success_count == 0

    def test_parallel_respects_max_parallel_tasks(self):
        from thinkai.agent.orchestrator import MultiAgentOrchestrator, AgentRole
        state = {"current": 0, "peak": 0}

        class SlowAgent:
            def __init__(self, name):
                self.name = name

            async def run(self, task, **kwargs):
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
                await asyncio.sleep(0.01)
                state["current"] -= 1
                return "done"

        orchestrator = MultiAgentOrchestrator(max_parallel_tasks=2)
        for i in range(6):
            orchestrator.add_agent(SlowAgent(f"a{i}"), role=AgentRole.WORKER)
        results = run_async(orchestrator.run_parallel([f"t{i}" for i in range(6)]))
        assert len(results) == 6
        assert state["peak"] <= 2, state["peak"]

    def test_status_reports_completed_tasks(self):
        from thinkai.agent.orchestrator import MultiAgentOrchestrator

        class EchoAgent:
            name = "echo"

            async def run(self, task, **kwargs):
                return "ok"

        orchestrator = MultiAgentOrchestrator()
        orchestrator.add_agent(EchoAgent())
        run_async(orchestrator.run_sequential(["a", "b"]))
        assert orchestrator.get_status()["completed_tasks"] == 2


class TestSandboxRegression:
    def test_concurrent_sandbox_calls_are_stable(self):
        from thinkai.skill import CodeSkill
        tool = CodeSkill().get_tools()[0]

        async def _run():
            return await asyncio.gather(*[
                tool.execute(code=f"result = {i} * 2") for i in range(8)
            ])

        assert run_async(_run()) == [str(i * 2) for i in range(8)]


class TestPersistenceRegression:
    def test_concurrent_writes_keep_json_valid(self, tmp_path):
        import json
        from thinkai.memory import FileMemoryStore, MemoryItem
        store = FileMemoryStore(base_path=str(tmp_path))

        async def _run():
            await asyncio.gather(*[
                store.save(MemoryItem(content=f"m{i}")) for i in range(20)
            ])

        run_async(_run())
        data = json.loads((tmp_path / "memories.json").read_text(encoding="utf-8"))
        assert len(data) == 20


class TestSkillSafetyRegression:
    def test_database_skill_readonly_rejects_writes(self):
        from thinkai.skill import DatabaseSkill
        tool = DatabaseSkill(readonly=True).get_tools()[0]
        result = run_async(tool.execute(query="DROP TABLE x"))
        assert "error" in result.lower() or "readonly" in result.lower()

    def test_api_skill_rejects_disallowed_host(self):
        from thinkai.skill import APISkill
        tool = APISkill(allowed_hosts=["example.com"]).get_tools()[0]
        result = run_async(tool.execute(method="GET", url="http://evil.com/x"))
        assert "denied" in result.lower() or "error" in result.lower()

    def test_image_skill_rejects_outside_path(self, tmp_path):
        from thinkai.skill import ImageSkill
        tool = ImageSkill(allowed_dirs=[str(tmp_path)]).get_tools()[0]
        result = run_async(tool.execute(file_path="C:/Windows/win.ini"))
        assert "denied" in result.lower() or "error" in result.lower()
