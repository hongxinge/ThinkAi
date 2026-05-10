"""日志中间件"""
import logging
from typing import Optional
from thinkai.core.models import ChatRequest, ChatResponse
from thinkai.middleware.base import BaseMiddleware


class LoggingMiddleware(BaseMiddleware):
    """日志中间件 - 记录请求和响应"""

    def __init__(self, logger: Optional[logging.Logger] = None, log_level: str = "INFO"):
        self.logger = logger or logging.getLogger("thinkai")
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)

    async def process_request(self, request: ChatRequest) -> ChatRequest:
        """记录请求"""
        self.logger.log(self.log_level, f"Chat request - model: {request.model}, messages: {len(request.messages)}")
        return request

    async def process_response(self, response: ChatResponse) -> ChatResponse:
        """记录响应"""
        usage_str = ""
        if response.usage:
            usage_str = f", tokens: {response.usage.total_tokens}"
        
        self.logger.log(
            self.log_level,
            f"Chat response - model: {response.model}{usage_str}",
        )
        return response

    async def process_error(self, error: Exception):
        """记录错误"""
        self.logger.error(f"Chat error: {str(error)}", exc_info=True)
