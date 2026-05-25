"""Embedding模块 - 文本向量化"""
from typing import List, Optional
import hashlib


class BaseEmbedding:
    """Embedding基类"""

    async def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed_text(t) for t in texts]


class SimpleHashEmbedding(BaseEmbedding):
    """
    轻量级哈希Embedding - 无需外部模型,开箱即用
    使用SimHash算法生成确定性向量,适合原型开发和测试
    生产环境建议替换为真实Embedding模型
    """

    def __init__(self, dim: int = 128):
        self.dim = dim

    async def embed_text(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vector(t) for t in texts]

    def _hash_to_vector(self, text: str) -> List[float]:
        words = text.lower().split()
        vector = [0.0] * self.dim
        for word in words:
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            for i in range(self.dim):
                if (h >> (i % 64)) & 1:
                    vector[i] += 1.0
                else:
                    vector[i] -= 1.0
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector


class OllamaEmbedding(BaseEmbedding):
    """Ollama Embedding - 使用本地模型生成向量"""

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def embed_text(self, text: str) -> List[float]:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("embeddings", [[]])[0]
            raise RuntimeError(f"Ollama embedding failed: {response.status_code}")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("embeddings", [])
            raise RuntimeError(f"Ollama embedding failed: {response.status_code}")


class OpenAIEmbedding(BaseEmbedding):
    """OpenAI Embedding - 使用OpenAI API生成向量"""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str = "", api_base: str = "https://api.openai.com/v1"):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base

    async def embed_text(self, text: str) -> List[float]:
        results = await self.embed_texts([text])
        return results[0] if results else []

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        import httpx
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.api_base}/embeddings",
                headers=headers,
                json={"model": self.model, "input": texts},
            )
            if response.status_code == 200:
                data = response.json()
                return [item["embedding"] for item in data.get("data", [])]
            raise RuntimeError(f"OpenAI embedding failed: {response.status_code}")


def create_embedding(
    provider: str = "simple",
    model: Optional[str] = None,
    **kwargs,
) -> BaseEmbedding:
    """
    创建Embedding实例

    Args:
        provider: Embedding提供者 (simple, ollama, openai)
        model: 模型名称
        **kwargs: 额外参数

    Returns:
        BaseEmbedding实例
    """
    if provider == "simple":
        return SimpleHashEmbedding(dim=kwargs.get("dim", 128))
    elif provider == "ollama":
        return OllamaEmbedding(
            model=model or "nomic-embed-text",
            base_url=kwargs.get("base_url", "http://localhost:11434"),
        )
    elif provider == "openai":
        return OpenAIEmbedding(
            model=model or "text-embedding-3-small",
            api_key=kwargs.get("api_key", ""),
            api_base=kwargs.get("api_base", "https://api.openai.com/v1"),
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
