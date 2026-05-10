"""会话管理器"""
from typing import Optional, List, Dict, Any
from thinkai.core.models import ChatMessage, MessageRole
from thinkai.core.config import SessionConfig
from thinkai.session.storage import BaseStorage
from thinkai.session.memory import MemoryStorage


class SessionManager:
    """
    会话管理器 - 管理多轮对话上下文
    """

    def __init__(self, config: SessionConfig):
        self.config = config
        self.storage: BaseStorage = self._init_storage()

    def _init_storage(self) -> BaseStorage:
        """初始化存储"""
        if self.config.storage == "memory":
            return MemoryStorage()
        elif self.config.storage == "redis":
            from thinkai.session.redis import RedisStorage
            return RedisStorage(url=self.config.redis_url)
        else:
            return MemoryStorage()

    async def get_messages(self, session_id: str) -> List[ChatMessage]:
        """获取会话消息"""
        messages_data = await self.storage.get(session_id)
        if not messages_data:
            return []
        
        return [ChatMessage(**msg) for msg in messages_data]

    async def add_message(self, session_id: str, message: ChatMessage):
        """添加消息"""
        if not self.config.enabled:
            return
        
        messages = await self.get_messages(session_id)
        messages.append(message)
        
        # 限制历史长度
        if len(messages) > self.config.max_history:
            # 保留system消息和最近的消息
            system_messages = [m for m in messages if m.role == MessageRole.SYSTEM]
            other_messages = [m for m in messages if m.role != MessageRole.SYSTEM]
            
            messages = system_messages + other_messages[-(self.config.max_history - len(system_messages)):]
        
        await self.storage.set(
            session_id,
            [m.to_dict() for m in messages],
            ttl=self.config.ttl,
        )

    async def add_and_get(
        self,
        session_id: str,
        new_messages: List[ChatMessage],
    ) -> List[ChatMessage]:
        """添加消息并返回完整历史"""
        messages = await self.get_messages(session_id)
        messages.extend(new_messages)
        
        # 限制历史长度
        if len(messages) > self.config.max_history:
            system_messages = [m for m in messages if m.role == MessageRole.SYSTEM]
            other_messages = [m for m in messages if m.role != MessageRole.SYSTEM]
            messages = system_messages + other_messages[-(self.config.max_history - len(system_messages)):]
        
        await self.storage.set(
            session_id,
            [m.to_dict() for m in messages],
            ttl=self.config.ttl,
        )
        
        return messages

    async def add_assistant_message(self, session_id: str, content: str):
        """添加助手消息"""
        message = ChatMessage.assistant(content)
        await self.add_message(session_id, message)

    async def delete_session(self, session_id: str):
        """删除会话"""
        await self.storage.delete(session_id)

    async def clear(self):
        """清空所有会话"""
        await self.storage.clear()

    async def close(self):
        """关闭会话管理器"""
        await self.storage.close()
