"""中间件基类"""
from abc import ABC, abstractmethod
from typing import List, Optional
from thinkai.core.models import ChatRequest, ChatResponse


class BaseMiddleware(ABC):
    """中间件基类"""

    @abstractmethod
    async def process_request(self, request: ChatRequest) -> ChatRequest:
        """处理请求"""
        pass

    @abstractmethod
    async def process_response(self, response: ChatResponse) -> ChatResponse:
        """处理响应"""
        pass

    async def process_error(self, error: Exception):
        """处理错误"""
        pass


class MiddlewareChain:
    """中间件链"""

    def __init__(self):
        self.middlewares: List[BaseMiddleware] = []

    def add(self, middleware: BaseMiddleware):
        """添加中间件"""
        self.middlewares.append(middleware)

    def remove(self, middleware: BaseMiddleware):
        """移除中间件"""
        if middleware in self.middlewares:
            self.middlewares.remove(middleware)

    def clear(self):
        """清空中间件"""
        self.middlewares.clear()

    def has_middlewares(self) -> bool:
        """检查是否有中间件"""
        return len(self.middlewares) > 0

    async def process_request(self, request: ChatRequest) -> ChatRequest:
        """处理请求链"""
        for middleware in self.middlewares:
            request = await middleware.process_request(request)
        return request

    async def process_response(self, response: ChatResponse) -> ChatResponse:
        """处理响应链(反向)"""
        for middleware in reversed(self.middlewares):
            response = await middleware.process_response(response)
        return response

    async def process_error(self, error: Exception):
        """处理错误链"""
        for middleware in self.middlewares:
            await middleware.process_error(error)
