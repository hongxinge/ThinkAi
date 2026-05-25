"""重试中间件"""
from typing import Tuple, Type
from thinkai.core.models import ChatRequest, ChatResponse
from thinkai.middleware.base import BaseMiddleware
from thinkai.exceptions import APIError, RateLimitError


class RetryMiddleware(BaseMiddleware):
    """重试中间件 - 配置重试策略,由ThinkAI客户端执行重试"""

    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        retryable_errors: Tuple[Type[Exception], ...] = (APIError, RateLimitError),
    ):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff_factor = backoff_factor
        self.retryable_errors = retryable_errors

    async def process_request(self, request: ChatRequest) -> ChatRequest:
        return request

    async def process_response(self, response: ChatResponse) -> ChatResponse:
        return response

    async def process_error(self, error: Exception):
        pass

    def is_retryable(self, error: Exception) -> bool:
        return isinstance(error, self.retryable_errors)

    def get_delay(self, attempt: int) -> float:
        return self.delay * (self.backoff_factor ** attempt)
