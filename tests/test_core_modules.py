"""核心模块全面测试 - 覆盖所有未测试的功能,严格匹配真实API"""
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


class TestExceptions:
    """异常模块测试"""

    def test_thinkai_error(self):
        from thinkai.exceptions import ThinkAiError
        err = ThinkAiError("test error")
        assert str(err) == "test error"
        assert err.code == "THINKAI_ERROR"

    def test_provider_not_found_error(self):
        from thinkai.exceptions import ProviderNotFoundError
        err = ProviderNotFoundError("unknown")
        assert "unknown" in str(err)
        assert err.code == "PROVIDER_NOT_FOUND"

    def test_custom_error_with_code(self):
        from thinkai.exceptions import ThinkAiError
        err = ThinkAiError("rate limited", code="RATE")
        assert err.code == "RATE"

    def test_error_inheritance(self):
        from thinkai.exceptions import ThinkAiError, ProviderNotFoundError, ConfigurationError
        assert issubclass(ProviderNotFoundError, ThinkAiError)
        assert issubclass(ConfigurationError, ThinkAiError)

    def test_api_errors(self):
        from thinkai.exceptions import APIConnectionError, APIError, RateLimitError, AuthenticationError
        err = APIConnectionError("timeout", "openai")
        assert "openai" in str(err)
        err = APIError("bad request", "openai", 400)
        assert "400" in str(err)
        err = RateLimitError("openai", retry_after=60)
        assert "60" in str(err)
        err = AuthenticationError("openai")
        assert "Authentication" in str(err)

    def test_model_and_session_errors(self):
        from thinkai.exceptions import ModelNotFoundError, SessionError, PromptError, RAGError, AgentError
        err = ModelNotFoundError("gpt-5", "openai")
        assert "gpt-5" in str(err)
        err = SessionError("session expired")
        assert err.code == "SESSION_ERROR"
        err = PromptError("invalid template")
        assert err.code == "PROMPT_ERROR"
        err = RAGError("index failed")
        assert err.code == "RAG_ERROR"
        err = AgentError("tool not found")
        assert err.code == "AGENT_ERROR"


class TestConfig:
    """配置管理测试"""

    def test_model_config(self):
        from thinkai.core.config import ModelConfig
        config = ModelConfig(provider="openai", api_key="test", model="gpt-4")
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_provider_config(self):
        from thinkai.core.config import ProviderConfig
        config = ProviderConfig(api_key="key", timeout=120, max_retries=5)
        assert config.api_key == "key"
        assert config.timeout == 120
        assert config.max_retries == 5

    def test_rag_config(self):
        from thinkai.core.config import RAGConfig
        config = RAGConfig()
        assert config.chunk_size == 500
        assert config.chunk_overlap == 50
        assert config.top_k == 5

    def test_session_config(self):
        from thinkai.core.config import SessionConfig
        config = SessionConfig()
        assert config.enabled is True
        assert config.max_history == 20
        assert config.ttl == 3600

    def test_agent_config(self):
        from thinkai.core.config import AgentConfig
        config = AgentConfig()
        assert config.enabled is False
        assert config.max_iterations == 10

    def test_settings_from_dict(self):
        from thinkai.core.config import Settings
        settings = Settings.from_dict({
            "default_provider": "openai",
            "default_model": "gpt-4",
        })
        assert settings.default_provider == "openai"
        assert settings.default_model == "gpt-4"

    def test_settings_default_values(self):
        from thinkai.core.config import Settings
        settings = Settings()
        assert settings.default_provider == "ollama"
        assert settings.default_model == "llama3"
        assert settings.debug is False

    def test_settings_to_dict(self):
        from thinkai.core.config import Settings
        settings = Settings(default_provider="openai", default_model="gpt-4")
        data = settings.to_dict()
        assert data["default_provider"] == "openai"
        assert data["default_model"] == "gpt-4"

    def test_settings_register_model(self):
        from thinkai.core.config import Settings
        settings = Settings()
        settings.register_model("my-model", {"provider": "openai", "model": "gpt-4"})
        config = settings.get_model_config("my-model")
        assert config.provider == "openai"
        assert config.model == "gpt-4"

    def test_settings_register_provider(self):
        from thinkai.core.config import Settings
        settings = Settings()
        settings.register_provider("my-provider", {"api_key": "test-key", "timeout": 120})
        config = settings.get_provider_config("my-provider")
        assert config.api_key == "test-key"
        assert config.timeout == 120

    def test_settings_get_default_model_config(self):
        from thinkai.core.config import Settings
        settings = Settings(default_provider="ollama", default_model="llama3")
        config = settings.get_model_config()
        assert config.provider == "ollama"
        assert config.model == "llama3"

    def test_settings_env_override(self):
        from thinkai.core.config import Settings
        import os
        os.environ["THINKAI_DEFAULT_PROVIDER"] = "openai"
        os.environ["THINKAI_DEFAULT_MODEL"] = "gpt-4o"
        settings = Settings()
        assert settings.default_provider == "openai"
        assert settings.default_model == "gpt-4o"
        del os.environ["THINKAI_DEFAULT_PROVIDER"]
        del os.environ["THINKAI_DEFAULT_MODEL"]


class TestModels:
    """数据模型测试"""

    def test_chat_message_user(self):
        from thinkai.core.models import ChatMessage, MessageRole
        msg = ChatMessage.user("Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_chat_message_system(self):
        from thinkai.core.models import ChatMessage, MessageRole
        msg = ChatMessage.system("You are helpful")
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are helpful"

    def test_chat_message_assistant(self):
        from thinkai.core.models import ChatMessage, MessageRole
        msg = ChatMessage.assistant("Hi there")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there"

    def test_chat_message_tool(self):
        from thinkai.core.models import ChatMessage, MessageRole
        msg = ChatMessage(role="tool", content="result", tool_call_id="call_123")
        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_123"

    def test_message_to_dict(self):
        from thinkai.core.models import ChatMessage
        msg = ChatMessage.user("test")
        data = msg.to_dict()
        assert data["role"] == "user"
        assert data["content"] == "test"

    def test_chat_request(self):
        from thinkai.core.models import ChatRequest, ChatMessage
        req = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage.user("test")],
            temperature=0.5,
            max_tokens=100,
        )
        assert req.model == "gpt-4"
        assert len(req.messages) == 1

    def test_chat_response(self):
        from thinkai.core.models import (
            ChatResponse, ChatMessage, ChatChoice, Usage, MessageRole
        )
        resp = ChatResponse(
            id="resp-123",
            model="gpt-4",
            choices=[ChatChoice(
                index=0,
                message=ChatMessage.assistant("Hello"),
                finish_reason="stop",
            )],
            usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
        assert resp.id == "resp-123"
        assert resp.message.content == "Hello"
        assert resp.usage.total_tokens == 30

    def test_stream_chunk(self):
        from thinkai.core.models import StreamChunk, StreamChoice, ChatMessage
        chunk = StreamChunk(
            id="chunk-1",
            model="gpt-4",
            choices=[StreamChoice(index=0, delta=ChatMessage.assistant("Hello"), finish_reason=None)],
        )
        assert chunk.id == "chunk-1"
        assert chunk.model == "gpt-4"
        assert len(chunk.choices) == 1
        assert chunk.choices[0].delta.content == "Hello"

    def test_tool_call_model(self):
        from thinkai.core.models import ToolCall, FunctionCall
        tc = ToolCall(
            id="call_1",
            type="function",
            function=FunctionCall(name="search", arguments='{"q": "test"}'),
        )
        assert tc.function.name == "search"

    def test_chat_request_with_tools(self):
        from thinkai.core.models import ChatRequest, ChatMessage, Tool, FunctionDefinition
        tool = Tool(
            type="function",
            function=FunctionDefinition(
                name="calculate",
                description="Calculate",
                parameters={"type": "object", "properties": {}},
            ),
        )
        req = ChatRequest(
            model="gpt-4",
            messages=[ChatMessage.user("1+1=?")],
            tools=[tool],
        )
        assert len(req.tools) == 1
        assert req.tools[0].function.name == "calculate"


class TestPromptTemplate:
    """Prompt模板测试"""

    def test_basic_template(self):
        from thinkai.prompt.template import PromptTemplate
        tpl = PromptTemplate(template="Hello, ${name}!")
        result = tpl.format(name="World")
        assert result == "Hello, World!"

    def test_template_multiple_vars(self):
        from thinkai.prompt.template import PromptTemplate
        tpl = PromptTemplate(template="I am ${name}, a ${role} at ${company}")
        result = tpl.format(name="Alice", role="engineer", company="ACME")
        assert "Alice" in result
        assert "engineer" in result
        assert "ACME" in result

    def test_prompt_manager(self):
        from thinkai.prompt.template import PromptManager
        manager = PromptManager()
        manager.register("greet", "Hello, ${person}!")
        result = manager.format("greet", **{"person": "Bob"})
        assert result == "Hello, Bob!"

    def test_builtin_templates(self):
        from thinkai.prompt.template import prompt_manager
        result = prompt_manager.format("rag_query", **{"context": "context info", "question": "my question"})
        assert "context info" in result
        assert "my question" in result

    def test_prompt_manager_missing_template(self):
        from thinkai.prompt.template import PromptManager
        from thinkai.exceptions import PromptError
        manager = PromptManager()
        with pytest.raises(PromptError):
            manager.format("nonexistent", **{"x": "test"})

    def test_prompt_manager_register_and_list(self):
        from thinkai.prompt.template import PromptManager
        manager = PromptManager()
        manager.register("test1", "template 1")
        manager.register("test2", "template 2")
        names = manager.list_templates()
        assert "test1" in names
        assert "test2" in names


class TestSessionManager:
    """会话管理测试"""

    def test_session_add_message(self):
        from thinkai.session.manager import SessionManager
        from thinkai.core.config import SessionConfig
        from thinkai.core.models import ChatMessage
        config = SessionConfig()
        mgr = SessionManager(config=config)
        sid = "test-session-1"
        run_async(mgr.add_message(sid, ChatMessage.user("Hello")))
        run_async(mgr.add_message(sid, ChatMessage.assistant("Hi")))
        messages = run_async(mgr.get_messages(sid))
        assert len(messages) == 2

    def test_session_get_nonexistent(self):
        from thinkai.session.manager import SessionManager
        from thinkai.core.config import SessionConfig
        config = SessionConfig()
        mgr = SessionManager(config=config)
        messages = run_async(mgr.get_messages("nonexistent"))
        assert messages == []

    def test_session_delete(self):
        from thinkai.session.manager import SessionManager
        from thinkai.core.config import SessionConfig
        from thinkai.core.models import ChatMessage
        config = SessionConfig()
        mgr = SessionManager(config=config)
        sid = "test-session-del"
        run_async(mgr.add_message(sid, ChatMessage.user("msg")))
        run_async(mgr.delete_session(sid))
        messages = run_async(mgr.get_messages(sid))
        assert messages == []

    def test_session_clear(self):
        from thinkai.session.manager import SessionManager
        from thinkai.core.config import SessionConfig
        from thinkai.core.models import ChatMessage
        config = SessionConfig()
        mgr = SessionManager(config=config)
        sid = "test-session-clear"
        run_async(mgr.add_message(sid, ChatMessage.user("msg")))
        run_async(mgr.clear())
        messages = run_async(mgr.get_messages(sid))
        assert messages == []

    def test_session_max_messages(self):
        from thinkai.session.manager import SessionManager
        from thinkai.core.config import SessionConfig
        from thinkai.core.models import ChatMessage
        config = SessionConfig(max_history=3)
        mgr = SessionManager(config=config)
        sid = "test-session-max"
        for i in range(5):
            run_async(mgr.add_message(sid, ChatMessage.user(f"msg{i}")))
        messages = run_async(mgr.get_messages(sid))
        assert len(messages) <= 3

    def test_session_context(self):
        from thinkai.session.manager import SessionManager
        from thinkai.core.config import SessionConfig
        from thinkai.session.context import SessionContext
        from thinkai import ThinkAI
        from thinkai.core.models import ChatMessage

        config = SessionConfig()
        mgr = SessionManager(config=config)
        ai = ThinkAI(provider="ollama", session_manager=mgr)
        sid = "test-session-ctx"

        async def test():
            ctx = SessionContext(client=ai, session_id=sid)
            ctx._initialized = True
            await ctx.client.session_manager.add_message(sid, ChatMessage.user("test"))
            msgs = await ctx.get_history()
            assert len(msgs) == 1

        run_async(test())

    def test_session_add_assistant_message(self):
        from thinkai.session.manager import SessionManager
        from thinkai.core.config import SessionConfig
        config = SessionConfig()
        mgr = SessionManager(config=config)
        sid = "test-assistant-msg"
        run_async(mgr.add_assistant_message(sid, "Hello from AI"))
        messages = run_async(mgr.get_messages(sid))
        assert len(messages) == 1
        assert messages[0].content == "Hello from AI"


class TestTextSplitter:
    """文本分割器测试"""

    def test_character_splitter_basic(self):
        from thinkai.rag.text_splitter import CharacterSplitter
        splitter = CharacterSplitter(chunk_size=10, chunk_overlap=2)
        text = "Hello World This Is A Test String"
        chunks = splitter.split(text)
        assert len(chunks) > 1
        assert all(len(c) <= 10 for c in chunks)

    def test_character_splitter_small_text(self):
        from thinkai.rag.text_splitter import CharacterSplitter
        splitter = CharacterSplitter(chunk_size=100, chunk_overlap=10)
        text = "Short text"
        chunks = splitter.split(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_character_splitter_empty_text(self):
        from thinkai.rag.text_splitter import CharacterSplitter
        splitter = CharacterSplitter(chunk_size=10, chunk_overlap=2)
        chunks = splitter.split("")
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_token_splitter_english(self):
        from thinkai.rag.text_splitter import TokenSplitter
        splitter = TokenSplitter(chunk_size=5, chunk_overlap=1)
        text = "The quick brown fox jumps over the lazy dog"
        chunks = splitter.split(text)
        assert len(chunks) > 1

    def test_token_splitter_count(self):
        from thinkai.rag.text_splitter import TokenSplitter
        splitter = TokenSplitter()
        count = splitter._count_tokens("hello world")
        assert count == 2

    def test_token_splitter_chinese(self):
        from thinkai.rag.text_splitter import TokenSplitter
        splitter = TokenSplitter()
        count = splitter._count_tokens("你好世界")
        assert count == 4

    def test_recursive_splitter_paragraphs(self):
        from thinkai.rag.text_splitter import RecursiveSplitter
        splitter = RecursiveSplitter(chunk_size=50, chunk_overlap=5)
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = splitter.split(text)
        assert len(chunks) >= 1
        assert all(len(c) <= 50 for c in chunks)

    def test_recursive_splitter_single_chunk(self):
        from thinkai.rag.text_splitter import RecursiveSplitter
        splitter = RecursiveSplitter(chunk_size=1000, chunk_overlap=50)
        text = "This is a short text that fits in one chunk."
        chunks = splitter.split(text)
        assert len(chunks) == 1

    def test_recursive_splitter_empty(self):
        from thinkai.rag.text_splitter import RecursiveSplitter
        splitter = RecursiveSplitter(chunk_size=100)
        chunks = splitter.split("")
        assert chunks == []


class TestDocumentLoader:
    """文档加载器测试"""

    def test_load_text_file(self):
        from thinkai.rag.document_loader import TextLoader
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, this is a test document.")
            f.flush()
            loader = TextLoader()
            docs = run_async(loader.load(f.name))
            assert len(docs) == 1
            assert "test document" in docs[0].content

    def test_load_nonexistent_file(self):
        from thinkai.rag.document_loader import TextLoader
        loader = TextLoader()
        docs = run_async(loader.load("/nonexistent/file.txt"))
        assert len(docs) == 0

    def test_multi_loader_txt(self):
        from thinkai.rag.document_loader import MultiLoader
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            f.flush()
            loader = MultiLoader()
            docs = run_async(loader.load(f.name))
            assert len(docs) == 1

    def test_document_metadata(self):
        from thinkai.rag.document_loader import Document
        doc = Document(content="test", metadata={"source": "test.txt"})
        assert doc.metadata["source"] == "test.txt"

    def test_document_str(self):
        from thinkai.rag.document_loader import Document
        doc = Document(content="short text content")
        s = str(doc)
        assert "Document" in s or "short" in s or "content" in s

    def test_multi_loader_markdown(self):
        from thinkai.rag.document_loader import MultiLoader
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\nContent here.")
            f.flush()
            loader = MultiLoader()
            docs = run_async(loader.load(f.name))
            assert len(docs) == 1


class TestMiddleware:
    """中间件测试"""

    def test_logging_middleware(self):
        from thinkai.middleware.logging_middleware import LoggingMiddleware
        middleware = LoggingMiddleware()
        assert middleware is not None

    def test_retry_middleware(self):
        from thinkai.middleware.retry_middleware import RetryMiddleware
        middleware = RetryMiddleware(max_retries=3, delay=0.1)
        assert middleware.max_retries == 3
        assert middleware.delay == 0.1

    def test_middleware_chain(self):
        from thinkai.middleware.base import MiddlewareChain, BaseMiddleware
        from thinkai.core.models import ChatRequest, ChatMessage

        class TestMiddleware(BaseMiddleware):
            async def process_request(self, request):
                request.messages.append(ChatMessage.system("injected"))
                return request

            async def process_response(self, response):
                return response

        chain = MiddlewareChain()
        chain.add(TestMiddleware())

        req = ChatRequest(model="test", messages=[ChatMessage.user("hello")])
        modified_req = run_async(chain.process_request(req))
        assert len(modified_req.messages) == 2

    def test_middleware_chain_empty(self):
        from thinkai.middleware.base import MiddlewareChain
        from thinkai.core.models import ChatRequest, ChatMessage

        chain = MiddlewareChain()
        req = ChatRequest(model="test", messages=[ChatMessage.user("hello")])
        result = run_async(chain.process_request(req))
        assert result == req

    def test_middleware_chain_response(self):
        from thinkai.middleware.base import MiddlewareChain, BaseMiddleware
        from thinkai.core.models import ChatResponse, ChatMessage, ChatChoice, Usage

        class ModMiddleware(BaseMiddleware):
            async def process_request(self, request):
                return request

            async def process_response(self, response):
                response.model = "modified"
                return response

        chain = MiddlewareChain()
        chain.add(ModMiddleware())

        resp = ChatResponse(
            id="test", model="original",
            choices=[ChatChoice(index=0, message=ChatMessage.assistant("hi"), finish_reason="stop")],
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
        result = run_async(chain.process_response(resp))
        assert result.model == "modified"

    def test_middleware_remove_and_clear(self):
        from thinkai.middleware.base import MiddlewareChain, BaseMiddleware
        from thinkai.core.models import ChatRequest, ChatResponse

        class NoopMiddleware(BaseMiddleware):
            async def process_request(self, request):
                return request
            async def process_response(self, response):
                return response

        chain = MiddlewareChain()
        m1 = NoopMiddleware()
        m2 = NoopMiddleware()
        chain.add(m1)
        chain.add(m2)
        assert chain.has_middlewares() is True
        chain.remove(m1)
        assert len(chain.middlewares) == 1
        chain.clear()
        assert chain.has_middlewares() is False


class TestProviderRegistry:
    """Provider注册表测试"""

    def test_registry_list(self):
        from thinkai.providers.registry import registry
        providers = registry.list()
        assert len(providers) > 0

    def test_get_provider(self):
        from thinkai.providers.registry import registry
        provider = registry.get("ollama")
        assert provider is not None

    def test_provider_names(self):
        from thinkai.providers.registry import registry
        names = registry.list()
        assert "ollama" in names

    def test_get_nonexistent_provider(self):
        from thinkai.providers.registry import registry
        result = registry.get("nonexistent_provider_xyz")
        assert result is None

    def test_custom_provider_registration(self):
        from thinkai.providers.registry import registry
        from thinkai.providers.base import BaseProvider

        class CustomProvider(BaseProvider):
            name = "custom_reg_test"
            default_model = "custom-model"
            default_api_base = "http://custom.api"

            async def chat(self, request):
                pass

            async def chat_stream(self, request):
                pass

        registry.register("custom_reg_test", CustomProvider)
        provider = registry.get("custom_reg_test")
        assert provider is not None
        assert provider.name == "custom_reg_test"


class TestStreaming:
    """流式处理测试"""

    def test_stream_handler(self):
        from thinkai.streaming import StreamHandler

        class MyHandler(StreamHandler):
            def __init__(self):
                self.chunks = []

            async def on_chunk(self, chunk):
                self.chunks.append(chunk)

            async def on_complete(self):
                pass

        handler = MyHandler()
        assert handler.chunks == []


class TestReActAgent:
    """ReAct Agent 测试"""

    def test_react_import(self):
        from thinkai.agent import ReActAgent
        assert ReActAgent is not None

    def test_react_creation(self):
        from thinkai.agent import ReActAgent
        from thinkai.skill import MathSkill

        agent = ReActAgent(
            name="test-react",
            tools=MathSkill().get_tools(),
            max_iterations=3,
        )
        assert agent.name == "test-react"
        assert agent.max_iterations == 3
        assert len(agent.tools) == 1

    def test_react_get_tool(self):
        from thinkai.agent import ReActAgent
        from thinkai.skill import MathSkill

        agent = ReActAgent(tools=MathSkill().get_tools())
        tool = agent.get_tool("calculate")
        assert tool is not None
        assert tool.name == "calculate"

    def test_react_get_tool_not_found(self):
        from thinkai.agent import ReActAgent
        agent = ReActAgent(tools=[])
        tool = agent.get_tool("nonexistent")
        assert tool is None

    def test_react_has_ai_client(self):
        from thinkai.agent import ReActAgent
        from thinkai.skill import MathSkill
        from thinkai import ThinkAI

        ai = ThinkAI(provider="ollama", model="llama3")
        agent = ReActAgent(ai_client=ai, tools=MathSkill().get_tools())
        assert agent.ai_client is ai


class TestAgentBase:
    """Agent 基类测试"""

    def test_agent_config(self):
        from thinkai.agent.base import AgentConfig
        config = AgentConfig(max_iterations=5)
        assert config.max_iterations == 5

    def test_agent_default_config(self):
        from thinkai.agent.base import AgentConfig
        config = AgentConfig()
        assert config.max_iterations == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
