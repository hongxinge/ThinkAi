"""向量存储抽象"""
from abc import ABC, abstractmethod
import math
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


class InMemoryVectorStore(BaseVectorStore):
    """
    内存向量存储 - 零依赖实现

    适合开发、测试与中小规模文档。纯Python余弦相似度计算,
    无需安装chromadb等外部服务。
    """

    def __init__(self):
        self._texts: List[str] = []
        self._embeddings: List[List[float]] = []
        self._metadatas: List[Dict] = []

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def add_documents(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict]] = None,
    ):
        """添加文档"""
        if len(texts) != len(embeddings):
            raise ValueError("texts与embeddings数量必须一致")
        self._texts.extend(texts)
        self._embeddings.extend(embeddings)
        self._metadatas.extend(metadatas or [{} for _ in texts])

    async def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索相似文档(余弦相似度)"""
        if not self._embeddings:
            return []
        scored = [
            (self._cosine_similarity(query_embedding, emb), i)
            for i, emb in enumerate(self._embeddings)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "content": self._texts[i],
                "metadata": self._metadatas[i] or {},
                "score": score,
                "id": str(i),
            }
            for score, i in scored[:top_k]
        ]

    async def delete(self, ids: List[str]):
        """删除文档(按id倒序删除,保持索引一致)"""
        for doc_id in sorted({int(i) for i in ids}, reverse=True):
            if 0 <= doc_id < len(self._texts):
                self._texts.pop(doc_id)
                self._embeddings.pop(doc_id)
                self._metadatas.pop(doc_id)

    async def clear(self):
        """清空存储"""
        self._texts.clear()
        self._embeddings.clear()
        self._metadatas.clear()
