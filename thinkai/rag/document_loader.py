"""文档加载器 - 支持多种文档格式"""
from abc import ABC, abstractmethod
from typing import List, Optional, Union
from pathlib import Path
import json


class Document:
    """文档数据类"""
    def __init__(self, content: str, metadata: Optional[dict] = None):
        self.content = content
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        return cls(
            content=data["content"],
            metadata=data.get("metadata", {}),
        )


class DocumentLoader(ABC):
    """文档加载器基类"""

    @abstractmethod
    async def load(self, source: str) -> List[Document]:
        """加载文档"""
        pass


class TextLoader(DocumentLoader):
    """文本文件加载器"""

    async def load(self, source: str) -> List[Document]:
        path = Path(source)
        
        if path.is_file():
            return [await self._load_file(path)]
        elif path.is_dir():
            docs = []
            for file_path in path.glob("**/*.txt"):
                docs.append(await self._load_file(file_path))
            return docs
        
        return []

    async def _load_file(self, path: Path) -> Document:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return Document(
            content=content,
            metadata={"source": str(path)},
        )


class MarkdownLoader(DocumentLoader):
    """Markdown文件加载器"""

    async def load(self, source: str) -> List[Document]:
        path = Path(source)
        
        if path.is_file() and path.suffix in [".md", ".markdown"]:
            return [await self._load_file(path)]
        elif path.is_dir():
            docs = []
            for file_path in path.glob("**/*.md"):
                docs.append(await self._load_file(file_path))
            return docs
        
        return []

    async def _load_file(self, path: Path) -> Document:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return Document(
            content=content,
            metadata={"source": str(path), "type": "markdown"},
        )


class JSONLoader(DocumentLoader):
    """JSON文件加载器"""

    async def load(self, source: str) -> List[Document]:
        path = Path(source)
        
        if not path.exists():
            return []
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return [
                Document(
                    content=item.get("content", json.dumps(item)),
                    metadata={"source": str(path), "index": i, **item.get("metadata", {})},
                )
                for i, item in enumerate(data)
            ]
        else:
            return [
                Document(
                    content=data.get("content", json.dumps(data)),
                    metadata={"source": str(path), **data.get("metadata", {})},
                )
            ]


class PDFLoader(DocumentLoader):
    """PDF文件加载器"""

    async def load(self, source: str) -> List[Document]:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf is required for PDF loading. Install with: pip install pypdf")
        
        path = Path(source)
        
        if path.is_file() and path.suffix == ".pdf":
            return [await self._load_file(path)]
        elif path.is_dir():
            docs = []
            for file_path in path.glob("**/*.pdf"):
                docs.append(await self._load_file(file_path))
            return docs
        
        return []

    async def _load_file(self, path: Path) -> Document:
        reader = PdfReader(str(path))
        content = []
        
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text.strip():
                content.append(text)
        
        return Document(
            content="\n\n".join(content),
            metadata={"source": str(path), "type": "pdf", "pages": len(reader.pages)},
        )


class MultiLoader(DocumentLoader):
    """多格式加载器"""

    def __init__(self):
        self.loaders = {
            ".txt": TextLoader(),
            ".md": MarkdownLoader(),
            ".markdown": MarkdownLoader(),
            ".json": JSONLoader(),
            ".pdf": PDFLoader(),
        }

    async def load(self, source: str) -> List[Document]:
        path = Path(source)
        
        if path.is_file():
            ext = path.suffix.lower()
            loader = self.loaders.get(ext)
            if loader:
                return await loader.load(source)
            else:
                # 默认使用文本加载器
                return await TextLoader().load(source)
        
        elif path.is_dir():
            all_docs = []
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    loader = self.loaders.get(ext)
                    if loader:
                        docs = await loader.load(str(file_path))
                        all_docs.extend(docs)
            return all_docs
        
        return []
