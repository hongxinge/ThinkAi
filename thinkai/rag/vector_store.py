"""向量存储抽象"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class BaseVectorStore(ABC):
    """向量存储基类"""

    @abstractmethod
    async def add_documents(self, texts: List[str], embeddings: List[List[float]], metadatas: Optional[List[Dict]] = None):
        """添加文档"""
        pass

    @abstractmethod
    async def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索相似文档"""
        pass

    @abstractmethod
    async def delete(self, ids: List[str]):
        """删除文档"""
        pass

    @abstractmethod
    async def clear(self):
        """清空存储"""
        pass
