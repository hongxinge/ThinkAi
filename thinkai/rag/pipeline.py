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
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        top_k: int = 5,
        embedding_model: str = "nomic-embed-text",
        embedding_provider: str = "simple",
        vector_store: str = "chroma",
        vector_store_path: str = "./thinkai_data/vectors",
        config: Optional[RAGConfig] = None,
        ai_client: Optional[Any] = None,
        embedding: Optional[BaseEmbedding] = None,
    ):
        self.config = config or RAGConfig()
        self.chunk_size = chunk_size or self.config.chunk_size
        self.chunk_overlap = chunk_overlap or self.config.chunk_overlap
        self.top_k = top_k or self.config.top_k
        self.embedding_model = embedding_model or self.config.embedding_model
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
        return ChromaStore(persist_path=path)

    def _init_embedding(self) -> BaseEmbedding:
        if self.ai_client and hasattr(self.ai_client, 'default_provider'):
            provider = self.ai_client.default_provider
            if provider == "ollama":
                return create_embedding("ollama", model=self.embedding_model)
            elif provider in ("openai", "deepseek", "qwen"):
                api_key = None
                if self.ai_client._main_provider:
                    api_key = self.ai_client._main_provider.api_key
                return create_embedding(
                    "openai",
                    model=self.embedding_model,
                    api_key=api_key or "",
                )
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
        if not self.indexed:
            return []

        k = top_k or self.top_k
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
