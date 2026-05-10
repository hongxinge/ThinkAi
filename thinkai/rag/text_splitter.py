"""文本分割器"""
from abc import ABC, abstractmethod
from typing import List
import re


class TextSplitter(ABC):
    """文本分割器基类"""

    @abstractmethod
    def split(self, text: str) -> List[str]:
        """分割文本"""
        pass


class CharacterSplitter(TextSplitter):
    """按字符分割"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap
        
        return chunks


class TokenSplitter(TextSplitter):
    """按Token分割(估算)"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _count_tokens(self, text: str) -> int:
        """简单估算token数(中英文混合)"""
        # 英文按空格分,中文按字符
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        return english_words + chinese_chars

    def split(self, text: str) -> List[str]:
        chunks = []
        words = text.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1
            if current_size + word_size > self.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # 保留重叠部分
                overlap_size = 0
                overlap_words = []
                for w in reversed(current_chunk):
                    if overlap_size + len(w) <= self.chunk_overlap:
                        overlap_words.insert(0, w)
                        overlap_size += len(w) + 1
                    else:
                        break
                current_chunk = overlap_words
                current_size = overlap_size
            
            current_chunk.append(word)
            current_size += word_size
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks


class RecursiveSplitter(TextSplitter):
    """递归分割器 - 优先按段落,然后按句子,最后按字符"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", "。", ".", "!", "!", "?", "?", " ", ""]

    def split(self, text: str) -> List[str]:
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """递归分割"""
        if not text:
            return []
        
        if len(text) <= self.chunk_size:
            return [text]
        
        separator = separators[0] if separators else ""
        remaining_separators = separators[1:]
        
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        
        # 如果分割后仍然太大,继续递归
        if len(splits) > 1 and any(len(s) > self.chunk_size for s in splits):
            return self._split_text(text, remaining_separators)
        
        # 合并小块
        return self._merge_splits(splits, separator)

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """合并分割结果"""
        chunks = []
        current_chunk = []
        current_length = 0
        
        for split in splits:
            split_with_sep = split + separator if separator else split
            split_len = len(split_with_sep)
            
            if current_length + split_len > self.chunk_size and current_chunk:
                chunks.append("".join(current_chunk))
                # 保留重叠
                overlap = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    if overlap_len + len(s) <= self.chunk_overlap:
                        overlap.insert(0, s)
                        overlap_len += len(s)
                    else:
                        break
                current_chunk = overlap
                current_length = overlap_len
            
            current_chunk.append(split_with_sep)
            current_length += split_len
        
        if current_chunk:
            chunks.append("".join(current_chunk))
        
        return chunks
