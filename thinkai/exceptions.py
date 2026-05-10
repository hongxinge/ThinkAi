"""ThinkAi核心异常定义"""
from typing import Optional


class ThinkAiError(Exception):
    """基础异常类"""
    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code or "THINKAI_ERROR"
        super().__init__(self.message)


class ProviderNotFoundError(ThinkAiError):
    """Provider未找到"""
    def __init__(self, provider: str):
        super().__init__(
            message=f"Provider '{provider}' not found. Available providers: {', '.join(get_available_providers())}",
            code="PROVIDER_NOT_FOUND"
        )


class ConfigurationError(ThinkAiError):
    """配置错误"""
    def __init__(self, message: str):
        super().__init__(message=message, code="CONFIG_ERROR")


class APIConnectionError(ThinkAiError):
    """API连接错误"""
    def __init__(self, message: str, provider: str):
        super().__init__(
            message=f"Failed to connect to {provider}: {message}",
            code="API_CONNECTION_ERROR"
        )


class APIError(ThinkAiError):
    """API调用错误"""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        status_msg = f" (Status: {status_code})" if status_code else ""
        super().__init__(
            message=f"API error from {provider}{status_msg}: {message}",
            code="API_ERROR"
        )


class RateLimitError(ThinkAiError):
    """速率限制错误"""
    def __init__(self, provider: str, retry_after: Optional[int] = None):
        retry_msg = f". Retry after {retry_after} seconds" if retry_after else ""
        super().__init__(
            message=f"Rate limit exceeded for {provider}{retry_msg}",
            code="RATE_LIMIT_ERROR"
        )


class AuthenticationError(ThinkAiError):
    """认证错误"""
    def __init__(self, provider: str):
        super().__init__(
            message=f"Authentication failed for {provider}. Please check your API key.",
            code="AUTH_ERROR"
        )


class ModelNotFoundError(ThinkAiError):
    """模型未找到"""
    def __init__(self, model: str, provider: str):
        super().__init__(
            message=f"Model '{model}' not found in provider '{provider}'",
            code="MODEL_NOT_FOUND"
        )


class SessionError(ThinkAiError):
    """会话错误"""
    def __init__(self, message: str):
        super().__init__(message=message, code="SESSION_ERROR")


class PromptError(ThinkAiError):
    """Prompt错误"""
    def __init__(self, message: str):
        super().__init__(message=message, code="PROMPT_ERROR")


class RAGError(ThinkAiError):
    """RAG错误"""
    def __init__(self, message: str):
        super().__init__(message=message, code="RAG_ERROR")


class AgentError(ThinkAiError):
    """Agent错误"""
    def __init__(self, message: str):
        super().__init__(message=message, code="AGENT_ERROR")


def get_available_providers() -> list:
    """获取可用的Provider列表"""
    from thinkai.providers.registry import registry
    return list(registry.providers.keys())
