"""重试中间件"""
import asyncio
from typing import Callable
from thinkai.core.models import ChatRequest, ChatResponse
from thinkai.middleware.base import BaseMiddleware
from thinkai.exceptions import APIError, RateLimitError


class RetryMiddleware(BaseMiddleware):
    """重试中间件 - 自动重试失败请求"""

    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        retryable_errors: tuple = (APIError, RateLimitError),
    ):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff_factor = backoff_factor
        self.retryable_errors = retryable_errors
        self._last_request = None
        self._request_func = None

    async def process_request(self, request: ChatRequest) -> ChatRequest:
        self._last_request = request
        return request

    async def process_response(self, response: ChatResponse) -> ChatResponse:
        return response

    async def process_error(self, error: Exception):
        """处理错误并重试"""
        if not isinstance(error, self.retryable_errors):
            raise error
        
        for attempt in range(self.max_retries):
            try:
                delay = self.delay * (self.backoff_factor ** attempt)
                await asyncio.sleep(delay)
                
                # 重新执行请求
                if self._request_func and self._last_request:
                    return await self._request_func(self._last_request)
            except self.retryable_errors:
                if attempt == self.max_retries - 1:
                    raise
