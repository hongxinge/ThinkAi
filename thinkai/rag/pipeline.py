"""RAG Pipeline - 检索增强生成"""
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from thinkai.core.models import ChatMessage
from thinkai.core.config import RAGConfig
from thinkai.rag.document_loader import Document, MultiLoader
from thinkai.rag.text_splitter import RecursiveSplitter, TextSplitter
from thinkai.rag.vector_store import BaseVectorStore
from thinkai.rag.chroma_store import ChromaStore
from thinkai.prompt.template import prompt_manager


class RAGPipeline:
    """
    RAG Pipeline - 3行代码实现检索增强生成
    
    使用示例:
        rag = RAGPipeline(
            documents=["./docs"],
            embedding_model="nomic-embed-text",
            vector_store="chroma"
        )
        
        response = await rag.query("如何配置?")
    """

    def __init__(
        self,
        documents: Optional[Union[str, List[str]]] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        top_k: int = 5,
        embedding_model: str = "nomic-embed-text",
        vector_store: str = "chroma",
        vector_store_path: str = "./thinkai_data/vectors",
        config: Optional[RAGConfig] = None,
        ai_client: Optional[Any] = None,
    ):
        """
        初始化RAG Pipeline
        
        Args:
            documents: 文档路径(文件或目录)
            chunk_size: 文本块大小
            chunk_overlap: 文本块重叠
            top_k: 检索返回的文档数量
            embedding_model: Embedding模型名称
            vector_store: 向量存储类型(chroma, faiss等)
            vector_store_path: 向量存储路径
            config: RAG配置
            ai_client: ThinkAI客户端实例(用于检索后生成)
        """
        self.config = config or RAGConfig()
        self.chunk_size = chunk_size or self.config.chunk_size
        self.chunk_overlap = chunk_overlap or self.config.chunk_overlap
        self.top_k = top_k or self.config.top_k
        self.embedding_model = embedding_model or self.config.embedding_model
        self.ai_client = ai_client
        
        # 初始化组件
        self.document_loader = MultiLoader()
        self.text_splitter = RecursiveSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        self.vector_store = self._init_vector_store(vector_store, vector_store_path)
        
        # 是否已索引
        self.indexed = False
        
        # 加载文档
        if documents:
            if isinstance(documents, str):
                documents = [documents]
            self.documents = documents
        else:
            self.documents = []

    def _init_vector_store(self, store_type: str, path: str) -> BaseVectorStore:
        """初始化向量存储"""
        if store_type == "chroma":
            return ChromaStore(persist_path=path)
        else:
            return ChromaStore(persist_path=path)

    async def load_and_split(self, documents: Optional[List[str]] = None):
        """
        加载并分割文档
        
        Args:
            documents: 文档路径列表
        """
        doc_paths = documents or self.documents
        if not doc_paths:
            raise ValueError("No documents provided")
        
        all_docs = []
        for doc_path in doc_paths:
            docs = await self.document_loader.load(doc_path)
            all_docs.extend(docs)
        
        # 分割文档
        chunks = []
        for doc in all_docs:
            split_texts = self.text_splitter.split(doc.content)
            for text in split_texts:
                chunks.append({
                    "text": text,
                    "metadata": doc.metadata,
                })
        
        return chunks

    async def index(self, documents: Optional[List[str]] = None):
        """
        索引文档
        
        Args:
            documents: 文档路径列表
        """
        chunks = await self.load_and_split(documents)
        
        # 这里应该生成embedding并存储到向量数据库
        # 由于embedding需要Provider支持,这里使用简化实现
        # 实际使用时需要调用embedding API
        
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
        
        # 生成查询embedding
        # 这里需要调用embedding API
        # 简化实现:直接返回空
        
        k = top_k or self.top_k
        # results = await self.vector_store.search(query_embedding, k)
        return []

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
        
        # 1. 检索相关文档
        context_docs = await self.retrieve(question, top_k)
        
        if not context_docs:
            # 没有检索到文档,直接提问
            return await self.ai_client.complete(question)
        
        # 2. 构建上下文
        context = "\n\n".join([doc["content"] for doc in context_docs])
        
        # 3. 构建增强Prompt
        template_name = prompt_template or "rag_query"
        prompt = prompt_manager.format(
            template_name,
            context=context,
            question=question,
        )
        
        # 4. 生成回答
        response = await self.ai_client.complete(prompt)
        
        return response

    async def add_document(self, document_path: str):
        """添加单个文档"""
        await self.index([document_path])

    async def clear(self):
        """清空索引"""
        await self.vector_store.clear()
        self.indexed = False
