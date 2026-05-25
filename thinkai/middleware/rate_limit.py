"""速率限制中间件"""
import asyncio
import time
import logging
from thinkai.core.models import ChatRequest, ChatResponse
from thinkai.middleware.base import BaseMiddleware
from thinkai.exceptions import RateLimitError

logger = logging.getLogger("thinkai")


class TokenBucketRateLimiter:
    """令牌桶速率限制器 - 平滑限流"""

    def __init__(self, rate: float = 1.0, capacity: int = 10):
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1):
        """等待直到令牌可用"""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
            wait_time = deficit / self.rate
            await asyncio.sleep(wait_time)

    async def try_acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌,不可用则立即返回False"""
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


class ConcurrentLimiter:
    """并发限制器 - 限制同时进行的API调用数"""

    def __init__(self, max_concurrent: int = 10):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

    async def __aenter__(self):
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._semaphore.release()
        return False


class RateLimitMiddleware(BaseMiddleware):
    """速率限制中间件 - 令牌桶限流 + 并发控制"""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst: int = 10,
        max_concurrent: int = 10,
    ):
        rate = requests_per_minute / 60.0
        self._bucket = TokenBucketRateLimiter(rate=rate, capacity=burst)
        self._concurrent = ConcurrentLimiter(max_concurrent=max_concurrent)
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.max_concurrent = max_concurrent

    async def process_request(self, request: ChatRequest) -> ChatRequest:
        """获取令牌并进入并发控制"""
        await self._bucket.acquire()
        await self._concurrent._semaphore.acquire()
        return request

    async def process_response(self, response: ChatResponse) -> ChatResponse:
        """释放并发信号量"""
        self._concurrent._semaphore.release()
        return response

    async def process_error(self, error: Exception):
        """释放并发信号量;若为RateLimitError则等待重试"""
        self._concurrent._semaphore.release()
        if isinstance(error, RateLimitError):
            retry_after = getattr(error, "retry_after", None) or 1
            logger.warning(f"Rate limit hit, waiting {retry_after}s before retry")
            await asyncio.sleep(retry_after)
