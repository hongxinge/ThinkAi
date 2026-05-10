"""Provider基类 - 定义统一接口"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncIterator, Union
import httpx
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from thinkai.core.models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    StreamChunk,
    Usage,
)
from thinkai.core.config import Settings, ModelConfig
from thinkai.exceptions import (
    ThinkAiError,
    APIConnectionError,
    APIError,
    AuthenticationError,
    RateLimitError,
)


class BaseProvider(ABC):
    """
    Provider基类 - 所有模型Provider必须继承此类
    提供统一的接口和通用功能
    """

    # Provider名称 - 子类必须覆盖
    name: str = "base"
    
    # 默认模型
    default_model: str = ""
    
    # 默认API基础URL
    default_api_base: str = ""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3,
        **kwargs,
    ):
        self.api_key = api_key
        self.api_base = api_base or self.default_api_base
        self.model = model or self.default_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra = kwargs
        
        # HTTP客户端
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端(单例模式)"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_base,
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头 - 子类可覆盖"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ThinkAi/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def close(self):
        """关闭HTTP客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abstractmethod
    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        """
        聊天接口 - 必须实现
        Args:
            request: 聊天请求
        Returns:
            聊天响应
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[StreamChunk]:
        """
        流式聊天接口 - 必须实现
        Args:
            request: 聊天请求
        Returns:
            流式响应迭代器
        """
        pass

    async def complete(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> ChatResponse:
        """
        简化的聊天方法
        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            model: 模型名称
            **kwargs: 额外参数
        Returns:
            聊天响应
        """
        request = ChatRequest(
            model=model or self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        
        return await self.execute_with_retry(self.chat, request)

    async def complete_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        简化的流式聊天方法
        """
        request = ChatRequest(
            model=model or self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )
        
        async for chunk in self.chat_stream(request):
            yield chunk

    async def execute_with_retry(self, func, *args, **kwargs):
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (APIConnectionError, RateLimitError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
            except Exception as e:
                raise
        
        raise last_error

    def _build_chat_request_payload(
        self,
        request: ChatRequest,
    ) -> Dict[str, Any]:
        """
        构建请求payload - 符合OpenAI标准
        子类可覆盖以适配不同API
        """
        payload = {
            "model": request.model or self.model,
            "messages": [msg.to_dict() for msg in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": request.stream,
        }
        
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.stop:
            payload["stop"] = request.stop
        if request.presence_penalty:
            payload["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty:
            payload["frequency_penalty"] = request.frequency_penalty
        if request.tools:
            payload["tools"] = [tool.model_dump() for tool in request.tools]
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        
        payload.update(request.extra)
        
        return payload

    def _parse_response(self, response_data: Dict[str, Any]) -> ChatResponse:
        """
        解析响应 - 默认按OpenAI格式解析
        子类可覆盖以适配不同API
        """
        return ChatResponse(
            id=response_data.get("id", ""),
            model=response_data.get("model", self.model),
            choices=[
                ChatChoice(
                    index=choice.get("index", 0),
                    message=ChatMessage(
                        role=choice["message"]["role"],
                        content=choice["message"].get("content"),
                    ),
                    finish_reason=choice.get("finish_reason"),
                )
                for choice in response_data.get("choices", [])
            ],
            usage=Usage.from_dict(response_data.get("usage", {})),
        )

    async def _handle_api_error(self, response: httpx.Response):
        """处理API错误响应"""
        if response.status_code == 401:
            raise AuthenticationError(self.name)
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(self.name, int(retry_after) if retry_after else None)
        elif response.status_code >= 400:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except:
                pass
            
            if response.status_code >= 500:
                raise APIConnectionError(error_msg, self.name)
            else:
                raise APIError(error_msg, self.name, response.status_code)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', model='{self.model}')"


class ProviderFactory:
    """
    Provider工厂 - 根据配置创建Provider实例
    """

    @staticmethod
    def create(provider_name: str, **kwargs) -> BaseProvider:
        """
        创建Provider实例
        Args:
            provider_name: Provider名称
            **kwargs: Provider配置参数
        Returns:
            Provider实例
        """
        from thinkai.providers.registry import registry
        
        provider_class = registry.get(provider_name)
        if provider_class is None:
            from thinkai.exceptions import ProviderNotFoundError
            raise ProviderNotFoundError(provider_name)
        
        return provider_class(**kwargs)

    @staticmethod
    def create_from_config(config: ModelConfig, **overrides) -> BaseProvider:
        """
        从配置创建Provider
        Args:
            config: 模型配置
            **overrides: 覆盖配置
        Returns:
            Provider实例
        """
        kwargs = {
            "api_key": config.api_key,
            "api_base": config.api_base,
            "model": config.model,
            "timeout": config.timeout,
        }
        kwargs.update(config.extra)
        kwargs.update(overrides)
        
        return ProviderFactory.create(config.provider, **kwargs)
