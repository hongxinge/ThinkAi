"""向量存储实现"""
from typing import List, Optional, Dict, Any
from pathlib import Path
from thinkai.rag.vector_store import BaseVectorStore


class ChromaStore(BaseVectorStore):
    """
    ChromaDB向量存储
    轻量级,适合本地开发
    """

    def __init__(self, collection_name: str = "thinkai", persist_path: str = "./thinkai_data/vectors"):
        try:
            import chromadb
        except ImportError:
            raise ImportError("chromadb is required. Install with: pip install chromadb")
        
        self.persist_path = persist_path
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def add_documents(self, texts: List[str], embeddings: List[List[float]], metadatas: Optional[List[Dict]] = None):
        """添加文档"""
        ids = [f"doc_{i}" for i in range(len(self.collection.ids()), len(self.collection.ids()) + len(texts))]
        
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )

    async def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索相似文档"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        
        docs = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                docs.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })
        
        return docs

    async def delete(self, ids: List[str]):
        """删除文档"""
        self.collection.delete(ids=ids)

    async def clear(self):
        """清空存储"""
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"},
        )
