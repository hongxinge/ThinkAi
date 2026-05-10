"""存储抽象基类"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class BaseStorage(ABC):
    """会话存储基类"""

    @abstractmethod
    async def get(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取会话消息"""
        pass

    @abstractmethod
    async def set(self, session_id: str, messages: List[Dict[str, Any]], ttl: int = 3600):
        """保存会话消息"""
        pass

    @abstractmethod
    async def delete(self, session_id: str):
        """删除会话"""
        pass

    @abstractmethod
    async def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        pass

    @abstractmethod
    async def clear(self):
        """清空所有会话"""
        pass

    @abstractmethod
    async def close(self):
        """关闭存储"""
        pass
