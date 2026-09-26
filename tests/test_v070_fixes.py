"""v0.7.0问题修复回归测试 - 覆盖全部21个已修复BUG的回归验证

覆盖修复点:
- 会话历史裁剪边界(负数切片失效)
- switch_provider真正生效
- FileMemoryStore写穿透落盘
- 限流x重试信号量对称获取/释放
- FileSkill路径前缀绕过
- 空agents层级编排
- RAG参数0值误回落
- InMemoryVectorStore
- MCP initialize握手/响应按id匹配/stderr排空
- Retry-After HTTP日期格式
- chat_stream会话支持+中间件对称
- CodeSkill超时保护+stdout捕获
- CharacterSplitter死循环
- plugin install_provider类型矛盾
- SDK异常映射裸raise
- payload extra下划线过滤
- FileCache枚举序列化
- 缓存命中短路Provider
- RedisStorage模块存在性
"""
import asyncio
import os
import sys
import tempfile
import json

import pytest

from thinkai.core.models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatChoice,
    StreamChunk,
    StreamChoice,
)
from thinkai.core.config import Settings, SessionConfig
from thinkai.exceptions import APIError, RateLimitError


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


def _make_response(content, model="test-model"):
    return ChatResponse(
        id="resp-1",
        model=model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage.assistant(content),
                finish_reason="stop",
            )
        ],
    )


# ---------------------------------------------------------------------------
# 测试用Fake Provider(注册到独立名称,不污染内置Provider)
# ---------------------------------------------------------------------------

from thinkai.providers.base import BaseProvider
from thinkai.providers.registry import registry as _provider_registry


class FakeStableProvider(BaseProvider):
    """稳定Provider - 每次返回相同内容并计数"""
    name = "v070-fake-stable"
    default_model = "fake-model"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_count = 0

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.call_count += 1
        return _make_response(f"echo: {request.messages[-1].content}")

    async def chat_stream(self, request: ChatRequest):
        for text in ["你好", "世界"]:
            yield StreamChunk(
                id="chunk-1",
                model="fake-model",
                choices=[
                    StreamChoice(
                        index=0,
                        delta=ChatMessage.assistant(text),
                        finish_reason=None,
                    )
                ],
            )


class FakeFlakyProvider(BaseProvider):
    """不稳定Provider - 第一次失败,重试后成功"""
    name = "v070-fake-flaky"
    default_model = "fake-model"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_count = 0

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.call_count += 1
        if self.call_count == 1:
            raise APIError("simulated failure", self.name, 500)
        return _make_response("recovered")

    async def chat_stream(self, request: ChatRequest):
        yield StreamChunk(
            id="chunk-1",
            model="fake-model",
            choices=[
                StreamChoice(index=0, delta=ChatMessage.assistant("s"), finish_reason=None)
            ],
        )


class FakeProviderA(BaseProvider):
    name = "v070-fake-a"
    default_model = "model-a"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_count = 0

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.call_count += 1
        return _make_response("from-a", model="model-a")

    async def chat_stream(self, request: ChatRequest):
        yield StreamChunk(
            id="c", model="model-a",
            choices=[StreamChoice(index=0, delta=ChatMessage.assistant("a"))],
        )


class FakeProviderB(BaseProvider):
    name = "v070-fake-b"
    default_model = "model-b"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_count = 0

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.call_count += 1
        return _make_response("from-b", model="model-b")

    async def chat_stream(self, request: ChatRequest):
        yield StreamChunk(
            id="c", model="model-b",
            choices=[StreamChoice(index=0, delta=ChatMessage.assistant("b"))],
        )


class FakePluginProvider(BaseProvider):
    """用于plugin install_provider测试 - entry_point动态定位本模块"""
    name = "v070-plugin-provider"
    default_model = "plugin-model"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return _make_response("plugin", model="plugin-model")

    async def chat_stream(self, request: ChatRequest):
        yield StreamChunk(
            id="c", model="plugin-model",
            choices=[StreamChoice(index=0, delta=ChatMessage.assistant("p"))],
        )


_provider_registry.register("v070-fake-stable", FakeStableProvider)
_provider_registry.register("v070-fake-flaky", FakeFlakyProvider)
_provider_registry.register("v070-fake-a", FakeProviderA)
_provider_registry.register("v070-fake-b", FakeProviderB)


# ---------------------------------------------------------------------------
# 1. 会话历史裁剪边界修复(原BUG: [-0:]返回全部消息)
# ---------------------------------------------------------------------------

class TestSessionHistoryTrim:
    def test_trim_when_system_count_reaches_limit(self):
        """system消息数 >= max_history时不得返回全部消息"""
        from thinkai.session.manager import SessionManager

        manager = SessionManager(SessionConfig(max_history=3))

        async def _run():
            # 3条system + 2条user,共5条 > max_history=3
            await manager.add_message("s", ChatMessage.system("sys1"))
            await manager.add_message("s", ChatMessage.system("sys2"))
            await manager.add_message("s", ChatMessage.system("sys3"))
            messages = await manager.add_and_get(
                "s", [ChatMessage.user("u1"), ChatMessage.user("u2")]
            )
            return messages

        messages = run_async(_run())
        # 修复前: [-0:]返回全部5条;修复后: 最多保留max_history=3条
        assert len(messages) <= 3
        assert all(m.role == "system" for m in messages)

    def test_trim_keeps_system_and_recent(self):
        """正常裁剪: 保留全部system消息 + 最近的其他消息"""
        from thinkai.session.manager import SessionManager

        manager = SessionManager(SessionConfig(max_history=4))

        async def _run():
            await manager.add_message("s2", ChatMessage.system("sys"))
            for i in range(6):
                await manager.add_message("s2", ChatMessage.user(f"u{i}"))
            return await manager.get_messages("s2")

        messages = run_async(_run())
        assert len(messages) == 4
        assert messages[0].role == "system"
        assert messages[0].content == "sys"
        # 保留最近的消息
        assert messages[-1].content == "u5"

    def test_no_trim_when_max_history_disabled(self):
        """max_history<=0时不裁剪"""
        from thinkai.session.manager import SessionManager

        manager = SessionManager(SessionConfig(max_history=0))

        async def _run():
            for i in range(10):
                await manager.add_message("s3", ChatMessage.user(f"m{i}"))
            return await manager.get_messages("s3")

        messages = run_async(_run())
        assert len(messages) == 10


# ---------------------------------------------------------------------------
# 2. switch_provider真正生效(原BUG: 切换后仍走旧Provider)
# ---------------------------------------------------------------------------

class TestSwitchProvider:
    def test_switch_provider_replaces_main_provider(self):
        from thinkai import ThinkAI

        ai = ThinkAI(provider="v070-fake-a", model="model-a")
        assert ai.default_provider == "v070-fake-a"
        assert isinstance(ai._main_provider, FakeProviderA)

        run_async(ai.switch_provider("v070-fake-b", model="model-b"))

        # 修复后: 实际Provider实例被替换
        assert ai.default_provider == "v070-fake-b"
        assert ai.default_model == "model-b"
        assert isinstance(ai._main_provider, FakeProviderB)

        # 实际请求必须走新Provider
        response = run_async(ai.chat("hello"))
        assert response.content == "from-b"
        assert ai._main_provider.call_count == 1

    def test_switch_provider_rollback_on_failure(self):
        from thinkai import ThinkAI

        ai = ThinkAI(provider="v070-fake-a", model="model-a")
        old_provider = ai._main_provider

        # 切换到不存在的Provider应失败并回滚
        with pytest.raises(Exception):
            run_async(ai.switch_provider("no-such-provider"))

        assert ai._main_provider is old_provider
        assert isinstance(old_provider, FakeProviderA)


# ---------------------------------------------------------------------------
# 3. FileMemoryStore写穿透落盘(原BUG: 只标脏不保存,退出即丢失)
# ---------------------------------------------------------------------------

class TestFileMemoryStorePersist:
    def test_save_persists_without_flush(self):
        from thinkai.memory import FileMemoryStore, MemoryItem

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(base_path=tmpdir)
            memory = MemoryItem(content="重要记忆", importance=0.9)

            async def _save():
                return await store.save(memory)

            memory_id = run_async(_save())
            # 不调用flush(),直接用新实例读取同一文件
            store2 = FileMemoryStore(base_path=tmpdir)

            async def _load():
                return await store2.get(memory_id)

            loaded = run_async(_load())
            assert loaded is not None
            assert loaded.content == "重要记忆"

    def test_delete_persists_without_flush(self):
        from thinkai.memory import FileMemoryStore, MemoryItem

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileMemoryStore(base_path=tmpdir)

            async def _run():
                mid = await store.save(MemoryItem(content="to-delete"))
                assert await store.delete(mid) is True

            run_async(_run())

            store2 = FileMemoryStore(base_path=tmpdir)

            async def _check():
                return await store2.search("to-delete")

            assert run_async(_check()) == []

    def test_memory_manager_roundtrip(self):
        from thinkai.memory import MemoryManager, FileMemoryStore

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(store=FileMemoryStore(base_path=tmpdir))

            async def _remember():
                return await manager.remember("用户喜欢蓝色", importance=0.8)

            run_async(_remember())

            # 新实例验证落盘
            manager2 = MemoryManager(store=FileMemoryStore(base_path=tmpdir))

            async def _recall():
                return await manager2.recall("蓝色")

            results = run_async(_recall())
            assert len(results) == 1
            assert results[0].content == "用户喜欢蓝色"


# ---------------------------------------------------------------------------
# 4. 限流x重试信号量对称(原BUG: process_error释放后重试不再获取,超额释放)
# ---------------------------------------------------------------------------

class TestRateLimitRetryBalance:
    def test_semaphore_stays_balanced_across_retries(self):
        from thinkai import ThinkAI
        from thinkai.middleware.rate_limit import RateLimitMiddleware
        from thinkai.middleware.retry_middleware import RetryMiddleware

        ai = ThinkAI(provider="v070-fake-flaky", model="fake-model")
        rate_limit_mw = RateLimitMiddleware(max_concurrent=1)
        retry_mw = RetryMiddleware(max_retries=2, delay=0.01, backoff_factor=1.0)
        ai.add_middleware(rate_limit_mw)
        ai.add_middleware(retry_mw)

        async def _run():
            r1 = await ai.chat("hello")
            r2 = await ai.chat("world")
            return r1, r2

        r1, r2 = run_async(_run())
        # 第一次chat内部重试后成功,第二次chat依然正常
        assert r1.content == "recovered"
        assert r2.content == "recovered"
        assert ai._main_provider.call_count == 3  # 失败1次 + 成功1次 + 第二次chat成功1次

        # 信号量计数必须恢复初始值: 超额释放会让value>1,限流失效
        semaphore = rate_limit_mw._concurrent._semaphore
        assert semaphore._value == 1


# ---------------------------------------------------------------------------
# 5. FileSkill路径前缀绕过(原BUG: startswith("/data")放行"/dataevil")
# ---------------------------------------------------------------------------

class TestFileSkillPathSecurity:
    def test_prefix_attack_blocked(self):
        from thinkai.skill import FileSkill

        with tempfile.TemporaryDirectory() as base:
            # 构造"/data"与"/dataevil"式相邻目录
            safe_dir = os.path.join(base, "data")
            evil_dir = os.path.join(base, "dataevil")
            os.makedirs(safe_dir)
            os.makedirs(evil_dir)
            with open(os.path.join(safe_dir, "ok.txt"), "w", encoding="utf-8") as f:
                f.write("safe content")
            with open(os.path.join(evil_dir, "secret.txt"), "w", encoding="utf-8") as f:
                f.write("secret content")

            skill = FileSkill(allowed_dirs=[safe_dir])
            tools = {t.name: t for t in skill.get_tools()}

            async def _run():
                # 合法路径正常读取
                ok_result = await tools["read_file"].execute(
                    file_path=os.path.join(safe_dir, "ok.txt")
                )
                assert "safe content" in ok_result

                # 前缀攻击必须被拒绝(修复前: startswith匹配被绕过)
                evil_result = await tools["read_file"].execute(
                    file_path=os.path.join(evil_dir, "secret.txt")
                )
                assert "Access denied" in evil_result
                assert "secret content" not in evil_result

            run_async(_run())

    def test_write_outside_blocked(self):
        from thinkai.skill import FileSkill

        with tempfile.TemporaryDirectory() as base:
            allowed = os.path.join(base, "allowed")
            os.makedirs(allowed)

            skill = FileSkill(allowed_dirs=[allowed])
            tools = {t.name: t for t in skill.get_tools()}

            async def _run():
                return await tools["write_file"].execute(
                    file_path=os.path.join(base, "outside.txt"), content="bad"
                )

            result = run_async(_run())
            assert "Access denied" in result
            assert not os.path.exists(os.path.join(base, "outside.txt"))


# ---------------------------------------------------------------------------
# 6. 空agents层级编排(原BUG: list(keys)[0]抛IndexError)
# ---------------------------------------------------------------------------

class TestHierarchicalEmptyAgents:
    def test_empty_agents_returns_error_not_crash(self):
        from thinkai.agent.orchestrator import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator(ai_client=None)
        result = run_async(orchestrator.run_hierarchical("some task"))
        assert "error" in result


# ---------------------------------------------------------------------------
# 7. RAG参数0值误回落修复 + InMemoryVectorStore
# ---------------------------------------------------------------------------

class TestRAGParamsAndMemoryStore:
    def test_zero_top_k_not_overridden(self):
        from thinkai.rag.pipeline import RAGPipeline
        from thinkai.core.config import RAGConfig

        # 显式传0不得回落到config默认值5
        pipeline = RAGPipeline(top_k=0, vector_store="memory")
        assert pipeline.top_k == 0

        # 不传时回落config
        config = RAGConfig(top_k=7)
        pipeline = RAGPipeline(config=config, vector_store="memory")
        assert pipeline.top_k == 7

    def test_invalid_vector_store_raises(self):
        from thinkai.rag.pipeline import RAGPipeline

        with pytest.raises(ValueError):
            RAGPipeline(vector_store="nonexistent")

    def test_in_memory_vector_store_roundtrip(self):
        from thinkai.rag.vector_store import InMemoryVectorStore

        async def _run():
            store = InMemoryVectorStore()
            await store.add_documents(
                ["文档一", "文档二"],
                [[1.0, 0.0], [0.0, 1.0]],
                [{"src": 1}, {"src": 2}],
            )
            results = await store.search([1.0, 0.0], top_k=2)
            assert len(results) == 2
            assert results[0]["content"] == "文档一"
            assert results[0]["score"] > 0.99
            assert results[0]["metadata"]["src"] == 1

            await store.delete(["1"])
            results = await store.search([0.0, 1.0], top_k=5)
            assert len(results) == 1
            assert results[0]["content"] == "文档一"

            await store.clear()
            assert await store.search([1.0, 0.0]) == []

        run_async(_run())

    def test_in_memory_vector_store_validation(self):
        from thinkai.rag.vector_store import InMemoryVectorStore

        async def _run():
            store = InMemoryVectorStore()
            with pytest.raises(ValueError):
                await store.add_documents(["a"], [[1.0], [2.0]])

        run_async(_run())


# ---------------------------------------------------------------------------
# 8. CharacterSplitter死循环修复(原BUG: overlap>=size时start不前进)
# ---------------------------------------------------------------------------

class TestCharacterSplitter:
    def test_overlap_geq_size_no_infinite_loop(self):
        from thinkai.rag.text_splitter import CharacterSplitter

        splitter = CharacterSplitter(chunk_size=10, chunk_overlap=50)
        chunks = splitter.split("x" * 100)
        assert len(chunks) > 0
        assert all(len(c) <= 10 for c in chunks)

    def test_invalid_params_clamped(self):
        from thinkai.rag.text_splitter import CharacterSplitter

        splitter = CharacterSplitter(chunk_size=0, chunk_overlap=-5)
        assert splitter.chunk_size >= 1
        assert splitter.chunk_overlap == 0
        chunks = splitter.split("y" * 30)
        assert len(chunks) >= 1

    def test_normal_split_with_overlap(self):
        from thinkai.rag.text_splitter import CharacterSplitter

        splitter = CharacterSplitter(chunk_size=10, chunk_overlap=3)
        text = "abcdefghij" * 3  # 30字符
        chunks = splitter.split(text)
        assert len(chunks) > 1
        # 重叠检验: 第二块开头应与前一块结尾重叠
        assert chunks[1][:3] == chunks[0][-3:]


# ---------------------------------------------------------------------------
# 9. CodeSkill: 超时保护 + stdout捕获(原BUG: 同步exec阻塞事件循环/无超时/print丢失)
# ---------------------------------------------------------------------------

class TestCodeSkillSandbox:
    def _get_tool(self, timeout=0.5):
        from thinkai.skill import CodeSkill
        skill = CodeSkill(timeout=timeout)
        return skill.get_tools()[0]

    def test_stdout_captured_in_result(self):
        tool = self._get_tool()
        result = run_async(tool.execute(code="print('hello sandbox'); result = 42"))
        assert "hello sandbox" in result
        assert "42" in result

    def test_explicit_result(self):
        tool = self._get_tool()
        result = run_async(tool.execute(code="result = 2 + 3"))
        assert result.strip() == "5"

    def test_timeout_returns_error_not_block(self):
        tool = self._get_tool(timeout=0.3)
        # 死循环代码必须被超时中止,不得阻塞事件循环
        result = run_async(tool.execute(code="while True: pass"))
        assert "TimeoutError" in result

    def test_import_blocked(self):
        tool = self._get_tool()
        result = run_async(tool.execute(code="import os"))
        assert "SafetyError" in result

    def test_syntax_error_reported(self):
        tool = self._get_tool()
        result = run_async(tool.execute(code="def broken(:"))
        assert "SyntaxError" in result


# ---------------------------------------------------------------------------
# 10. Retry-After HTTP日期格式(原BUG: int("Wed, 21 Oct...")抛ValueError)
# ---------------------------------------------------------------------------

class TestRetryAfterHeader:
    def _provider(self):
        class _P(BaseProvider):
            name = "test"

            async def chat(self, request):
                pass

            async def chat_stream(self, request):
                yield

        return _P()

    def test_http_date_retry_after_ignored(self):
        import httpx

        provider = self._provider()
        response = httpx.Response(
            429,
            headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
        )

        async def _run():
            await provider._handle_api_error(response)

        # 修复前: int(日期)抛ValueError掩盖真实错误;修复后: 抛RateLimitError
        with pytest.raises(RateLimitError):
            run_async(_run())

    def test_numeric_retry_after_kept(self):
        import httpx

        provider = self._provider()
        response = httpx.Response(429, headers={"Retry-After": "5"})

        async def _run():
            await provider._handle_api_error(response)

        with pytest.raises(RateLimitError) as exc_info:
            run_async(_run())
        assert "5 seconds" in str(exc_info.value.message)


# ---------------------------------------------------------------------------
# 11. chat_stream: session支持 + 中间件对称
# ---------------------------------------------------------------------------

class TestChatStreamEnhanced:
    def test_stream_saves_session_and_releases_semaphore(self):
        from thinkai import ThinkAI
        from thinkai.middleware.rate_limit import RateLimitMiddleware

        ai = ThinkAI(provider="v070-fake-stable", model="fake-model")
        rate_limit_mw = RateLimitMiddleware(max_concurrent=1)
        ai.add_middleware(rate_limit_mw)

        async def _run():
            chunks = []
            async for chunk in ai.chat_stream("你好世界", session_id="v070-stream-sess"):
                if chunk.choices and chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
            return chunks

        collected = run_async(_run())
        assert "".join(collected) == "你好世界"

        # 流结束后会话历史: user + assistant
        messages = run_async(ai.session_manager.get_messages("v070-stream-sess"))
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[1].content == "你好世界"

        # 中间件资源对称释放
        assert rate_limit_mw._concurrent._semaphore._value == 1

        run_async(ai.session_manager.delete_session("v070-stream-sess"))


# ---------------------------------------------------------------------------
# 12. 缓存: FileCache枚举序列化 + 命中短路Provider
# ---------------------------------------------------------------------------

class TestCacheIntegration:
    def test_file_cache_serializes_model_with_enum(self):
        """原BUG: model_dump()的枚举role无法json.dump,FileCache报TypeError"""
        from thinkai.cache import CacheMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            mw = CacheMiddleware(backend="file", cache_dir=tmpdir)

            req = ChatRequest(model="m", messages=[ChatMessage.user("hi")])
            resp = _make_response("cached answer")

            async def _run():
                await mw.process_request(req)
                await mw.store_response(req, resp)
                # 用相同内容的新请求验证命中
                req2 = ChatRequest(model="m", messages=[ChatMessage.user("hi")])
                await mw.process_request(req2)
                return CacheMiddleware.get_cached_response(req2)

            cached = run_async(_run())
            assert cached is not None
            assert cached["choices"][0]["message"]["content"] == "cached answer"

    def test_chat_hits_cache_without_calling_provider(self):
        from thinkai import ThinkAI
        from thinkai.cache import CacheMiddleware

        ai = ThinkAI(provider="v070-fake-stable", model="fake-model")
        ai.add_middleware(CacheMiddleware(backend="memory"))

        async def _run():
            r1 = await ai.chat("same question")
            r2 = await ai.chat("same question")
            return r1, r2

        r1, r2 = run_async(_run())
        assert r1.content == r2.content == "echo: same question"
        # 原BUG: 缓存中间件从不被查询,每次都打Provider;修复后第二次命中缓存
        assert ai._main_provider.call_count == 1


# ---------------------------------------------------------------------------
# 13. payload extra下划线过滤(原BUG: 缓存内部标记污染API载荷)
# ---------------------------------------------------------------------------

class TestPayloadExtraFilter:
    def test_underscore_extra_excluded_from_payload(self):
        provider = FakeStableProvider()
        request = ChatRequest(
            model="m",
            messages=[ChatMessage.user("hi")],
            extra={"_cache_key": "internal", "_cache_hit": True, "custom_param": "yes"},
        )
        payload = provider._build_chat_request_payload(request)
        assert "_cache_key" not in payload
        assert "_cache_hit" not in payload
        assert payload["custom_param"] == "yes"


# ---------------------------------------------------------------------------
# 14. MCP客户端: initialize握手/响应id匹配/超时/stderr排空
# ---------------------------------------------------------------------------

_FAKE_MCP_SERVER = """
import sys, json

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\\n")
    sys.stdout.flush()

line = sys.stdin.readline()
req = json.loads(line)
assert req["method"] == "initialize", req["method"]
send({"jsonrpc": "2.0", "id": req["id"], "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "fake", "version": "1.0"},
}})

for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    msg = json.loads(raw)
    method = msg.get("method")
    mid = msg.get("id")
    if method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [
            {"name": "echo", "description": "Echo tool", "inputSchema": {"type": "object"}},
        ]}})
    elif method == "tools/call":
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": "hello from mcp"}],
        }})
    sys.stderr.write("server log line\\n")
    sys.stderr.flush()
"""


class TestMCPClient:
    def test_full_handshake_and_tool_call(self):
        from thinkai.mcp import MCPServerClient

        client = MCPServerClient(
            command=sys.executable,
            args=["-c", _FAKE_MCP_SERVER],
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
            timeout=10.0,
        )

        async def _run():
            try:
                # connect()完成initialize握手,严格Server要求握手后才接受tools/list
                await client.connect()
                tools = await client.list_tools()
                assert len(tools) == 1
                assert tools[0].name == "echo"
                assert tools[0].to_openai_format()["function"]["name"] == "echo"

                result = await client.call_tool("echo", {"text": "hi"})
                assert "hello from mcp" in result
            finally:
                await client.close()

        run_async(_run())

    def test_request_timeout_raises(self):
        from thinkai.mcp import MCPServerClient

        # Server不响应任何请求 -> 超时;stdin关闭后自然退出,便于close()快速清理
        silent_server = "import sys\nfor _ in iter(sys.stdin.readline, ''):\n    pass\n"
        client = MCPServerClient(
            command=sys.executable,
            args=["-c", silent_server],
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
            timeout=0.3,
        )

        async def _run():
            try:
                with pytest.raises(RuntimeError) as exc_info:
                    await client.connect()
                assert "timed out" in str(exc_info.value) or "closed" in str(exc_info.value)
            finally:
                await client.close()

        run_async(_run())


# ---------------------------------------------------------------------------
# 15. plugin install_provider修复(原BUG: 实例vs类型检查矛盾,必失败)
# ---------------------------------------------------------------------------

class TestPluginInstallProvider:
    def test_install_provider_registers_class(self):
        from thinkai.plugin import PluginManager, PluginInfo
        from thinkai.providers.registry import ProviderRegistry

        pm = PluginManager()
        entry_point = f"{FakePluginProvider.__module__}:{FakePluginProvider.__qualname__}"
        pm.register(PluginInfo(
            name="v070-plugin-prov",
            version="1.0.0",
            description="test provider plugin",
            plugin_type="provider",
            entry_point=entry_point,
        ))

        reg = ProviderRegistry()
        # 修复前: isinstance(instance, type)永远False,必然抛TypeError
        instance = pm.install_provider("v070-plugin-prov", reg)

        assert isinstance(instance, FakePluginProvider)
        assert reg.get("v070-plugin-prov") is FakePluginProvider


# ---------------------------------------------------------------------------
# 16. SDK异常映射裸raise修复(原BUG: 脱离except上下文调用抛RuntimeError)
# ---------------------------------------------------------------------------

class TestMapSdkException:
    def test_non_api_error_reraised_verbatim(self):
        try:
            import openai  # noqa: F401
        except ImportError:
            pytest.skip("openai SDK not installed")

        from thinkai.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
        provider.name = "test"

        original = ValueError("boom")
        with pytest.raises(ValueError) as exc_info:
            provider._map_sdk_exception(original)

        # 原异常原样抛出(修复前裸raise在无except上下文时抛RuntimeError)
        assert exc_info.value is original

    def test_openai_provider_same_behavior(self):
        try:
            import openai  # noqa: F401
        except ImportError:
            pytest.skip("openai SDK not installed")

        from thinkai.providers.openai import OpenAIProvider

        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.name = "test"

        original = KeyError("missing")
        with pytest.raises(KeyError):
            provider._map_sdk_exception(original)


# ---------------------------------------------------------------------------
# 17. RedisStorage模块存在(原BUG: manager.py引用不存在的模块,ImportError)
# ---------------------------------------------------------------------------

class TestRedisStorageModule:
    def test_module_importable(self):
        try:
            from thinkai.session.redis import RedisStorage
        except ImportError as e:
            if "redis" in str(e) and "pip install" in str(e):
                pytest.skip("redis package not installed")
            raise

        # 构造不发起真实连接(redis.asyncio.from_url为惰性连接)
        storage = RedisStorage(url="redis://127.0.0.1:6379/0")
        assert storage.prefix == "thinkai:session:"

    def test_missing_url_raises_friendly_config_error(self):
        """redis_url未配置时给出友好的配置错误提示,而非redis库裸ValueError"""
        try:
            from thinkai.session.redis import RedisStorage
        except ImportError as e:
            if "redis" in str(e) and "pip install" in str(e):
                pytest.skip("redis package not installed")
            raise

        from thinkai.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            RedisStorage(url=None)
        assert "redis_url" in str(exc_info.value.message)

        with pytest.raises(ConfigurationError):
            RedisStorage(url="http://wrong-scheme:6379")

    def test_storage_dispatch_in_manager(self):
        """manager按配置正确分发到redis存储(仅验证分发逻辑,不连接)"""
        from thinkai.session.manager import SessionManager
        from thinkai.session.storage import BaseStorage

        try:
            import redis  # noqa: F401
        except ImportError:
            pytest.skip("redis package not installed")

        manager = SessionManager(
            SessionConfig(storage="redis", redis_url="redis://127.0.0.1:6379/0")
        )
        assert isinstance(manager.storage, BaseStorage)
        assert type(manager.storage).__name__ == "RedisStorage"


# ---------------------------------------------------------------------------
# 18. 综合回归: 完整chat流程(中间件链+会话+缓存)
# ---------------------------------------------------------------------------

class TestChatFullPipeline:
    def test_chat_with_session_and_middlewares(self):
        from thinkai import ThinkAI
        from thinkai.middleware.rate_limit import RateLimitMiddleware
        from thinkai.middleware.retry_middleware import RetryMiddleware
        from thinkai.middleware.logging_middleware import LoggingMiddleware

        ai = ThinkAI(provider="v070-fake-stable", model="fake-model")
        ai.add_middleware(LoggingMiddleware())
        ai.add_middleware(RateLimitMiddleware(max_concurrent=2))
        ai.add_middleware(RetryMiddleware(max_retries=1, delay=0.001))

        async def _run():
            r1 = await ai.chat("第一问", session_id="v070-pipe")
            r2 = await ai.chat("第二问", session_id="v070-pipe")
            return r1, r2

        r1, r2 = run_async(_run())
        assert r1.content == "echo: 第一问"
        assert r2.content == "echo: 第二问"

        # 会话历史完整: 2问 + 2答
        messages = run_async(ai.session_manager.get_messages("v070-pipe"))
        assert len(messages) == 4

        run_async(ai.session_manager.delete_session("v070-pipe"))
