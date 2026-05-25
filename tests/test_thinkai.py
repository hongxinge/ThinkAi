"""ThinkAi框架测试用例"""
import asyncio
import pytest
from thinkai import ThinkAI, Settings, SessionManager, PromptTemplate
from thinkai.core.models import ChatMessage, MessageRole, ChatRequest, ChatResponse, ChatChoice, Usage, StreamChunk, StreamChoice
from thinkai.providers.registry import registry
from thinkai.prompt.template import prompt_manager


class TestThinkAICore:
    """ThinkAI核心功能测试"""

    def test_import(self):
        """测试导入"""
        import thinkai
        assert hasattr(thinkai, '__version__')
        assert thinkai.__version__ == "0.6.0"

    def test_create_client(self):
        """测试创建客户端"""
        ai = ThinkAI(provider="ollama", model="llama3")
        assert ai is not None
        assert ai.default_provider == "ollama"
        assert ai.default_model == "llama3"

    def test_list_providers(self):
        """测试列出Provider"""
        ai = ThinkAI()
        providers = ai.list_providers()
        assert "ollama" in providers
        assert "openai" in providers
        assert "qwen" in providers
        assert "deepseek" in providers

    def test_register_model(self):
        """测试注册模型"""
        ai = ThinkAI()
        ai.register_model("gpt4", provider="openai", model="gpt-4")
        models = ai.list_models()
        assert "gpt4" in models
        assert models["gpt4"]["provider"] == "openai"


class TestConfig:
    """配置管理测试"""

    def test_default_settings(self):
        """测试默认配置"""
        settings = Settings()
        assert settings.default_provider == "ollama"
        assert settings.default_model == "llama3"

    def test_settings_from_dict(self):
        """测试从字典创建配置"""
        config = {
            "default_provider": "openai",
            "default_model": "gpt-4",
        }
        settings = Settings.from_dict(config)
        assert settings.default_provider == "openai"
        assert settings.default_model == "gpt-4"


class TestModels:
    """数据模型测试"""

    def test_chat_message_user(self):
        """测试用户消息"""
        msg = ChatMessage.user("你好")
        assert msg.role == MessageRole.USER
        assert msg.content == "你好"

    def test_chat_message_system(self):
        """测试系统消息"""
        msg = ChatMessage.system("你是一个助手")
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "你是一个助手"

    def test_chat_message_assistant(self):
        """测试助手消息"""
        msg = ChatMessage.assistant("你好,我是助手")
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "你好,我是助手"

    def test_message_to_dict(self):
        """测试消息转字典"""
        msg = ChatMessage.user("测试")
        data = msg.to_dict()
        assert data["role"] == "user"
        assert data["content"] == "测试"

    def test_chat_request(self):
        """测试聊天请求"""
        messages = [ChatMessage.user("你好")]
        request = ChatRequest(
            model="llama3",
            messages=messages,
            temperature=0.7,
        )
        assert request.model == "llama3"
        assert len(request.messages) == 1

    def test_chat_response(self):
        """测试聊天响应"""
        response = ChatResponse(
            id="test-123",
            model="llama3",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage.assistant("你好"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
        assert response.content == "你好"
        assert response.usage.total_tokens == 30


class TestPromptTemplate:
    """Prompt模板测试"""

    def test_basic_template(self):
        """测试基础模板"""
        template = PromptTemplate("你好,$name")
        result = template.format(name="世界")
        assert result == "你好,世界"

    def test_template_multiple_vars(self):
        """测试多变量模板"""
        template = PromptTemplate("$a + $b = $c")
        result = template.format(a="1", b="2", c="3")
        assert result == "1 + 2 = 3"

    def test_prompt_manager(self):
        """测试Prompt管理器"""
        templates = prompt_manager.list_templates()
        assert len(templates) > 0

    def test_builtin_templates(self):
        """测试内置模板"""
        assert prompt_manager.get("system_default") is not None
        assert prompt_manager.get("rag_query") is not None


class TestSessionManager:
    """会话管理测试"""

    @pytest.mark.asyncio
    async def test_session_create(self):
        """测试会话创建"""
        from thinkai.core.config import SessionConfig
        config = SessionConfig()
        manager = SessionManager(config)
        assert manager is not None
        await manager.close()

    @pytest.mark.asyncio
    async def test_session_add_message(self):
        """测试添加消息"""
        from thinkai.core.config import SessionConfig
        config = SessionConfig()
        manager = SessionManager(config)
        
        msg = ChatMessage.user("测试消息")
        await manager.add_message("test-session", msg)
        
        messages = await manager.get_messages("test-session")
        assert len(messages) == 1
        assert messages[0].content == "测试消息"
        
        await manager.close()


class TestProviderRegistry:
    """Provider注册表测试"""

    def test_registry_available(self):
        """测试注册表可用"""
        assert registry is not None
        assert len(registry.providers) > 0

    def test_get_provider(self):
        """测试获取Provider"""
        ollama_class = registry.get("ollama")
        assert ollama_class is not None
        
        openai_class = registry.get("openai")
        assert openai_class is not None

    def test_provider_names(self):
        """测试Provider名称"""
        providers = registry.list()
        assert "ollama" in providers
        assert "openai" in providers
        assert "qwen" in providers
        assert "deepseek" in providers


class TestMiddleware:
    """中间件测试"""

    def test_middleware_chain(self):
        """测试中间件链"""
        from thinkai.middleware.base import MiddlewareChain
        chain = MiddlewareChain()
        assert not chain.has_middlewares()

    def test_logging_middleware(self):
        """测试日志中间件"""
        from thinkai.middleware import LoggingMiddleware
        middleware = LoggingMiddleware()
        assert middleware is not None


class TestExceptions:
    """异常测试"""

    def test_thinkai_error(self):
        """测试基础异常"""
        from thinkai.exceptions import ThinkAiError
        error = ThinkAiError("测试错误")
        assert error.message == "测试错误"
        assert error.code == "THINKAI_ERROR"

    def test_provider_not_found_error(self):
        """测试Provider未找到异常"""
        from thinkai.exceptions import ProviderNotFoundError
        try:
            raise ProviderNotFoundError("unknown")
        except ProviderNotFoundError as e:
            assert "unknown" in e.message


class TestStreaming:
    """流式处理测试"""

    @pytest.mark.asyncio
    async def test_stream_handler(self):
        """测试流式处理器"""
        from thinkai.streaming import StreamHandler
        
        async def mock_chunks():
            yield StreamChunk(
                id="test",
                model="llama3",
                choices=[StreamChoice(delta=ChatMessage.assistant(content="Hello"))]
            )
            yield StreamChunk(
                id="test",
                model="llama3",
                choices=[StreamChoice(delta=ChatMessage.assistant(content=" World"))]
            )
        
        result = await StreamHandler.to_string(mock_chunks())
        assert result == "Hello World"


def run_tests():
    """运行测试"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()
