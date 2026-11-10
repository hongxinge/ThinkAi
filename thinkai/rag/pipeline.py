"""RAG Pipeline - 检索增强生成"""
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from thinkai.core.models import ChatMessage
from thinkai.core.config import RAGConfig
from thinkai.rag.document_loader import Document, MultiLoader
from thinkai.rag.text_splitter import RecursiveSplitter, TextSplitter
from thinkai.rag.vector_store import BaseVectorStore
from thinkai.rag.chroma_store import ChromaStore
from thinkai.rag.embedding import BaseEmbedding, SimpleHashEmbedding, create_embedding
from thinkai.prompt.template import prompt_manager


class RAGPipeline:
    """
    RAG Pipeline - 3行代码实现检索增强生成

    使用示例:
        rag = RAGPipeline(
            documents=["./docs"],
            ai_client=ai,
        )
        await rag.index()
        response = await rag.query("如何配置?")
    """

    def __init__(
        self,
        documents: Optional[Union[str, List[str]]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        top_k: Optional[int] = None,
        embedding_model: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        vector_store: str = "memory",
        vector_store_path: str = "./thinkai_data/vectors",
        config: Optional[RAGConfig] = None,
        ai_client: Optional[Any] = None,
        embedding: Optional[BaseEmbedding] = None,
    ):
        self.config = config or RAGConfig()
        # 未显式传入时回落到配置值(None判断保证0等合法值不被误覆盖)
        self.chunk_size = chunk_size if chunk_size is not None else self.config.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else self.config.chunk_overlap
        self.top_k = top_k if top_k is not None else self.config.top_k
        self.embedding_model = embedding_model if embedding_model is not None else self.config.embedding_model
        self.embedding_provider = embedding_provider
        self.ai_client = ai_client

        self.document_loader = MultiLoader()
        self.text_splitter = RecursiveSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        self.vector_store = self._init_vector_store(vector_store, vector_store_path)

        self.embedding = embedding or self._init_embedding()

        self.indexed = False
        self._chunk_metadata: List[Dict[str, Any]] = []

        if documents:
            if isinstance(documents, str):
                documents = [documents]
            self.documents = documents
        else:
            self.documents = []

    def _init_vector_store(self, store_type: str, path: str) -> BaseVectorStore:
        if store_type == "chroma":
            return ChromaStore(persist_path=path)
        elif store_type == "memory":
            from thinkai.rag.vector_store import InMemoryVectorStore
            return InMemoryVectorStore()
        raise ValueError(
            f"不支持的向量存储类型: {store_type}, 可选: chroma, memory"
        )

    def _init_embedding(self) -> BaseEmbedding:
        # 显式指定时优先（旧实现完全忽略 embedding_provider 参数）
        if self.embedding_provider is not None:
            return create_embedding(
                self.embedding_provider, model=self.embedding_model
            )

        # 自动推断：仅 Ollama 有确定的本地 embedding 端点。
        if (
            self.ai_client
            and getattr(self.ai_client, "default_provider", None) == "ollama"
        ):
            return create_embedding("ollama", model=self.embedding_model)

        # 其余 Provider 的 embedding 端点与模型名并不通用（旧实现会把
        # Ollama 的 nomic-embed-text 发给 api.openai.com/v1），
        # 因此默认回落到零依赖哈希实现；需要语义向量时请显式指定
        # embedding_provider 与 embedding_model。
        return create_embedding("simple")

    async def load_and_split(self, documents: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        doc_paths = documents or self.documents
        if not doc_paths:
            raise ValueError("No documents provided")

        all_docs = []
        for doc_path in doc_paths:
            docs = await self.document_loader.load(doc_path)
            all_docs.extend(docs)

        chunks = []
        for doc in all_docs:
            split_texts = self.text_splitter.split(doc.content)
            for i, text in enumerate(split_texts):
                chunks.append({
                    "text": text,
                    "metadata": {**doc.metadata, "chunk_index": i},
                })

        return chunks

    async def index(self, documents: Optional[List[str]] = None):
        """
        索引文档 - 生成embedding并存入向量数据库

        Args:
            documents: 文档路径列表
        """
        chunks = await self.load_and_split(documents)
        if not chunks:
            self.indexed = True
            return

        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        embeddings = await self.embedding.embed_texts(texts)

        await self.vector_store.add_documents(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        # 二次索引（add_document）应追加而非覆盖，保持元数据与向量库一致
        if self.indexed:
            self._chunk_metadata.extend(metadatas)
        else:
            self._chunk_metadata = metadatas
        self.indexed = True

    async def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 返回文档数量

        Returns:
            相关文档列表
        """
        # 不再以实例内 indexed 标志短路：持久化向量库（如 ChromaStore）
        # 在新进程/新实例中同样应当可检索；空库由向量存储自行返回 []。
        k = top_k if top_k is not None else self.top_k
        query_embedding = await self.embedding.embed_text(query)
        results = await self.vector_store.search(query_embedding, k)
        return results

    async def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        prompt_template: Optional[str] = None,
    ) -> str:
        """
        完整的RAG查询流程

        Args:
            question: 问题
            top_k: 检索文档数量
            prompt_template: Prompt模板名称

        Returns:
            回答
        """
        if not self.ai_client:
            raise ValueError("ai_client is required for RAG query")

        context_docs = await self.retrieve(question, top_k)

        if not context_docs:
            response = await self.ai_client.chat(question)
            return response.content

        context = "\n\n".join([doc.get("content", doc.get("text", "")) for doc in context_docs])

        template_name = prompt_template or "rag_query"
        prompt = prompt_manager.format(
            template_name,
            context=context,
            question=question,
        )

        response = await self.ai_client.chat(prompt)
        return response.content

    async def add_document(self, document_path: str):
        await self.index([document_path])

    async def clear(self):
        await self.vector_store.clear()
        self._chunk_metadata = []
        self.indexed = False
