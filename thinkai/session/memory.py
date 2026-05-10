"""内存存储实现"""
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime, timedelta
from thinkai.session.storage import BaseStorage


class MemoryStorage(BaseStorage):
    """
    内存会话存储
    适用于开发和测试,生产环境建议使用Redis或数据库
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取会话消息"""
        async with self._lock:
            session = self._store.get(session_id)
            if not session:
                return None
            
            # 检查TTL
            if session["expires_at"] < datetime.now():
                del self._store[session_id]
                return None
            
            return session["messages"]

    async def set(self, session_id: str, messages: List[Dict[str, Any]], ttl: int = 3600):
        """保存会话消息"""
        async with self._lock:
            self._store[session_id] = {
                "messages": messages,
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(seconds=ttl),
            }

    async def delete(self, session_id: str):
        """删除会话"""
        async with self._lock:
            self._store.pop(session_id, None)

    async def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        async with self._lock:
            session = self._store.get(session_id)
            if not session:
                return False
            
            if session["expires_at"] < datetime.now():
                del self._store[session_id]
                return False
            
            return True

    async def clear(self):
        """清空所有会话"""
        async with self._lock:
            self._store.clear()

    async def close(self):
        """关闭存储"""
        await self.clear()

    def size(self) -> int:
        """获取会话数量"""
        return len(self._store)
