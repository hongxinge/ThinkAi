"""会话上下文管理器"""
from typing import Optional, List, TYPE_CHECKING
from thinkai.core.models import ChatMessage

if TYPE_CHECKING:
    from thinkai.core.client import ThinkAI


class SessionContext:
    """
    会话上下文管理器
    提供便捷的会话内连续对话
    """

    def __init__(self, client: "ThinkAI", session_id: Optional[str] = None):
        self.client = client
        self.session_id = session_id or self._generate_id()
        self._initialized = False

    def _generate_id(self) -> str:
        import uuid
        return f"session-{uuid.uuid4().hex[:8]}"

    async def __aenter__(self):
        self._initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._initialized = False

    async def chat(
        self,
        message: str,
        **kwargs,
    ):
        """在会话中聊天"""
        if not self._initialized:
            raise RuntimeError("SessionContext must be used as async context manager")
        
        return await self.client.chat(
            messages=message,
            session_id=self.session_id,
            **kwargs,
        )

    async def complete(
        self,
        message: str,
        **kwargs,
    ) -> str:
        """在会话中聊天并返回文本"""
        response = await self.chat(message, **kwargs)
        return response.content or ""

    async def get_history(self) -> List[ChatMessage]:
        """获取会话历史"""
        if self.client.session_manager:
            return await self.client.session_manager.get_messages(self.session_id)
        return []

    async def clear_history(self):
        """清空会话历史"""
        if self.client.session_manager:
            await self.client.session_manager.delete_session(self.session_id)

    def __repr__(self) -> str:
        return f"SessionContext(id='{self.session_id}')"
