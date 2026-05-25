"""ThinkAI统一客户端 - 开发者主要入口"""
from typing import Optional, List, Dict, Any, Union, AsyncIterator
from contextlib import asynccontextmanager
import asyncio
import json

from thinkai.core.config import Settings, ModelConfig
from thinkai.core.models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    StreamChunk,
    MessageRole,
)
from thinkai.providers.base import BaseProvider, ProviderFactory
from thinkai.providers.registry import registry
from thinkai.session.manager import SessionManager
from thinkai.middleware import MiddlewareChain
from thinkai.middleware.retry_middleware import RetryMiddleware
from thinkai.exceptions import ThinkAiError


class ThinkAI:
    """
    ThinkAI统一客户端 - 简单易用的AI框架入口
    
    使用示例:
        # 最简使用
        ai = ThinkAI()
        response = await ai.chat("你好")
        
        # 指定Provider
        ai = ThinkAI(provider="ollama", model="llama3")
        
        # 多模型管理
        ai = ThinkAI()
        ai.register_model("qwen", provider="qwen", model="qwen-turbo")
        response = await ai.chat("你好", model="qwen")
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "llama3",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        config: Optional[Settings] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: int = 60,
        max_retries: int = 3,
        **kwargs,
    ):
        """
        初始化ThinkAI客户端
        
        Args:
            provider: Provider名称 (ollama, openai, qwen, deepseek等)
            model: 模型名称
            api_key: API密钥
            api_base: API基础URL
            config: 全局配置对象
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 超时时间(秒)
            max_retries: 最大重试次数
        """
        # 加载配置
        self.config = config or Settings()
        
        # 主Provider
        self.default_provider = provider
        self.default_model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Provider实例缓存
        self._providers: Dict[str, BaseProvider] = {}
        self._main_provider: Optional[BaseProvider] = None
        
        # 会话管理
        self.session_manager: Optional[SessionManager] = None
        if self.config.session.enabled:
            self.session_manager = SessionManager(self.config.session)
        
        # 中间件链
        self.middleware_chain = MiddlewareChain()
        
        # 模型路由配置
        self._model_aliases: Dict[str, str] = {}
        
        # 初始化主Provider
        self._init_main_provider(
            api_key=api_key,
            api_base=api_base,
            **kwargs,
        )

    def _init_main_provider(self, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        """初始化主Provider"""
        provider_key = api_key or self.config.get_provider_config(self.default_provider).api_key
        provider_base = api_base or self.config.get_provider_config(self.default_provider).api_base
        
        self._main_provider = ProviderFactory.create(
            self.default_provider,
            api_key=provider_key,
            api_base=provider_base,
            model=self.default_model,
            timeout=self.timeout,
            max_retries=self.max_retries,
            **kwargs,
        )

    def _get_provider(self, model: Optional[str] = None) -> BaseProvider:
        """
        获取Provider实例
        
        Args:
            model: 模型名称或别名
            
        Returns:
            Provider实例
        """
        if not model or model == self.default_model:
            return self._main_provider
        
        # 检查是否是别名
        model = self._model_aliases.get(model, model)
        
        # 检查是否已缓存
        if model in self._providers:
            return self._providers[model]
        
        # 从配置创建
        if model in self.config.models:
            model_config = self.config.models[model]
            provider = ProviderFactory.create_from_config(model_config)
            self._providers[model] = provider
            return provider
        
        # 使用默认Provider
        return self._main_provider

    def register_provider(
        self,
        name: str,
        provider_class: type,
        **kwargs,
    ):
        """
        注册自定义Provider
        
        Args:
            name: Provider名称
            provider_class: Provider类
            **kwargs: Provider配置
        """
        registry.register(name, provider_class)

    def register_model(
        self,
        name: str,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        """
        注册模型配置
        
        Args:
            name: 模型名称/别名
            provider: Provider名称
            model: 实际模型名称
            api_key: API密钥
            api_base: API基础URL
            **kwargs: 额外配置
        """
        self.config.register_model(name, {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "api_base": api_base,
            **kwargs,
        })

    def add_alias(self, alias: str, model_name: str):
        """添加模型别名"""
        self._model_aliases[alias] = model_name

    def add_middleware(self, middleware):
        """添加中间件"""
        self.middleware_chain.add(middleware)

    def _get_retry_middleware(self) -> Optional[RetryMiddleware]:
        for mw in self.middleware_chain.middlewares:
            if isinstance(mw, RetryMiddleware):
                return mw
        return None

    async def chat(
        self,
        messages: Union[str, List[ChatMessage]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        session_id: Optional[str] = None,
        tools: Optional[List] = None,
        **kwargs,
    ) -> ChatResponse:
        if isinstance(messages, str):
            messages = [ChatMessage.user(messages)]

        if session_id and self.session_manager:
            messages = await self.session_manager.add_and_get(
                session_id, messages
            )

        request = ChatRequest(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            tools=tools,
            **kwargs,
        )

        if self.middleware_chain.has_middlewares():
            request = await self.middleware_chain.process_request(request)

        provider = self._get_provider(request.model)
        retry_mw = self._get_retry_middleware()
        max_attempts = (retry_mw.max_retries + 1) if retry_mw else 1
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                response = await provider.chat(request)

                if self.middleware_chain.has_middlewares():
                    response = await self.middleware_chain.process_response(response)

                if session_id and self.session_manager and response.choices:
                    await self.session_manager.add_assistant_message(
                        session_id,
                        response.content,
                    )

                return response
            except Exception as e:
                last_error = e
                if self.middleware_chain.has_middlewares():
                    await self.middleware_chain.process_error(e)
                if retry_mw and retry_mw.is_retryable(e) and attempt < max_attempts - 1:
                    delay = retry_mw.get_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise

        raise last_error

    async def chat_stream(
        self,
        messages: Union[str, List[ChatMessage]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        流式聊天接口
        
        Args:
            messages: 消息内容
            model: 模型名称/别名
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 额外参数
            
        Returns:
            AsyncIterator[StreamChunk]: 流式响应迭代器
        """
        if isinstance(messages, str):
            messages = [ChatMessage.user(messages)]
        
        request = ChatRequest(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            stream=True,
            **kwargs,
        )
        
        provider = self._get_provider(request.model)
        
        async for chunk in provider.chat_stream(request):
            yield chunk

    async def complete(
        self,
        messages: Union[str, List[ChatMessage]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        简化聊天方法 - 直接返回文本内容
        
        Args:
            messages: 消息内容
            model: 模型名称/别名
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 额外参数
            
        Returns:
            str: 响应文本
        """
        response = await self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.content or ""

    async def switch_provider(self, provider: str, model: Optional[str] = None):
        """
        切换Provider
        
        Args:
            provider: 新Provider名称
            model: 新模型名称(可选)
        """
        self.default_provider = provider
        if model:
            self.default_model = model
        
        self._main_provider = self._get_provider(model)

    @asynccontextmanager
    async def session(self, session_id: Optional[str] = None):
        """
        会话上下文管理器
        
        使用示例:
            async with ai.session() as sess:
                response1 = await sess.chat("你好")
                response2 = await sess.chat("你呢?")
        """
        from thinkai.session.context import SessionContext
        async with SessionContext(self, session_id) as ctx:
            yield ctx

    def list_providers(self) -> Dict[str, type]:
        """列出所有可用的Provider"""
        return registry.list()

    def list_models(self) -> Dict[str, Dict[str, Any]]:
        """列出所有已注册的模型"""
        models = {}
        for name, config in self.config.models.items():
            models[name] = {
                "provider": config.provider,
                "model": config.model,
            }
        return models

    async def close(self):
        """关闭所有Provider连接"""
        if self._main_provider:
            await self._main_provider.close()
        
        for provider in self._providers.values():
            await provider.close()
        
        if self.session_manager:
            await self.session_manager.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __repr__(self) -> str:
        return f"ThinkAI(provider='{self.default_provider}', model='{self.default_model}')"
