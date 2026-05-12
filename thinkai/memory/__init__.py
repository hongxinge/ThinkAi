"""Agent记忆系统 - 长期记忆和跨会话记忆"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import os
from pathlib import Path


class MemoryItem:
    """记忆项"""

    def __init__(
        self,
        content: str,
        memory_type: str = "fact",
        importance: float = 0.5,
        timestamp: Optional[datetime] = None,
        source: str = "conversation",
        tags: Optional[List[str]] = None,
    ):
        self.content = content
        self.memory_type = memory_type  # fact, preference, experience, context
        self.importance = importance  # 0.0-1.0
        self.timestamp = timestamp or datetime.now()
        self.source = source
        self.tags = tags or []
        self.access_count = 0
        self.last_accessed = self.timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "tags": self.tags,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        item = cls(
            content=data["content"],
            memory_type=data.get("memory_type", "fact"),
            importance=data.get("importance", 0.5),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "conversation"),
            tags=data.get("tags", []),
        )
        item.access_count = data.get("access_count", 0)
        item.last_accessed = datetime.fromisoformat(data["last_accessed"])
        return item

    def __repr__(self) -> str:
        return f"MemoryItem(content='{self.content[:50]}...', type={self.memory_type}, importance={self.importance})"


class MemoryStore:
    """记忆存储后端 - 抽象接口"""

    async def save(self, memory: MemoryItem) -> str:
        raise NotImplementedError

    async def get(self, memory_id: str) -> Optional[MemoryItem]:
        raise NotImplementedError

    async def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        raise NotImplementedError

    async def list_by_type(self, memory_type: str, limit: int = 50) -> List[MemoryItem]:
        raise NotImplementedError

    async def delete(self, memory_id: str) -> bool:
        raise NotImplementedError

    async def clear(self) -> None:
        raise NotImplementedError


class FileMemoryStore(MemoryStore):
    """基于文件的记忆存储 - 简单持久化"""

    def __init__(self, base_path: str = "./memory"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._memories: Dict[str, MemoryItem] = {}
        self._load()

    def _load(self):
        """从文件加载记忆"""
        memory_file = self.base_path / "memories.json"
        if memory_file.exists():
            with open(memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item_data in data:
                    memory = MemoryItem.from_dict(item_data)
                    self._memories[memory.content[:32] + str(memory.timestamp.timestamp())] = memory

    def _save_to_file(self):
        """保存到文件"""
        memory_file = self.base_path / "memories.json"
        data = [m.to_dict() for m in self._memories.values()]
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def save(self, memory: MemoryItem) -> str:
        memory_id = memory.content[:32] + str(memory.timestamp.timestamp())
        self._memories[memory_id] = memory
        self._save_to_file()
        return memory_id

    async def get(self, memory_id: str) -> Optional[MemoryItem]:
        return self._memories.get(memory_id)

    async def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        query_lower = query.lower()
        results = []
        for memory in self._memories.values():
            if query_lower in memory.content.lower() or query_lower in " ".join(memory.tags).lower():
                results.append(memory)
        results.sort(key=lambda m: m.importance * (1 + m.access_count * 0.1), reverse=True)
        for m in results[:limit]:
            m.access_count += 1
            m.last_accessed = datetime.now()
        return results[:limit]

    async def list_by_type(self, memory_type: str, limit: int = 50) -> List[MemoryItem]:
        results = [m for m in self._memories.values() if m.memory_type == memory_type]
        results.sort(key=lambda m: m.importance, reverse=True)
        return results[:limit]

    async def delete(self, memory_id: str) -> bool:
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save_to_file()
            return True
        return False

    async def clear(self) -> None:
        self._memories.clear()
        self._save_to_file()


class MemoryManager:
    """记忆管理器 - 统一记忆接口"""

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        max_memories: int = 100,
        enable_forgetting: bool = True,
        forgetting_threshold: float = 0.2,
    ):
        self.store = store or FileMemoryStore()
        self.max_memories = max_memories
        self.enable_forgetting = enable_forgetting
        self.forgetting_threshold = forgetting_threshold

    async def remember(
        self,
        content: str,
        memory_type: str = "fact",
        importance: float = 0.5,
        source: str = "conversation",
        tags: Optional[List[str]] = None,
    ) -> str:
        """记住信息"""
        memory = MemoryItem(
            content=content,
            memory_type=memory_type,
            importance=importance,
            source=source,
            tags=tags,
        )
        memory_id = await self.store.save(memory)
        await self._cleanup_if_needed()
        return memory_id

    async def recall(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """回忆/检索记忆"""
        return await self.store.search(query, limit=limit)

    async def get_facts(self, limit: int = 20) -> List[MemoryItem]:
        """获取事实记忆"""
        return await self.store.list_by_type("fact", limit=limit)

    async def get_preferences(self, limit: int = 20) -> List[MemoryItem]:
        """获取偏好记忆"""
        return await self.store.list_by_type("preference", limit=limit)

    async def get_experiences(self, limit: int = 20) -> List[MemoryItem]:
        """获取经验记忆"""
        return await self.store.list_by_type("experience", limit=limit)

    async def forget_low_importance(self) -> int:
        """遗忘低重要性记忆"""
        all_memories = []
        for memory_type in ["fact", "preference", "experience", "context"]:
            all_memories.extend(await self.store.list_by_type(memory_type, limit=1000))

        to_delete = [m for m in all_memories if m.importance < self.forgetting_threshold and m.access_count == 0]

        deleted = 0
        for memory in to_delete:
            memory_id = memory.content[:32] + str(memory.timestamp.timestamp())
            if await self.store.delete(memory_id):
                deleted += 1

        return deleted

    async def build_context_prompt(self, query: str, max_tokens: int = 1000) -> str:
        """构建记忆上下文Prompt"""
        relevant = await self.recall(query, limit=10)
        if not relevant:
            return ""

        context_lines = ["# 相关记忆\n"]
        total_len = len(context_lines[0])

        for i, memory in enumerate(relevant):
            line = f"{i+1}. [{memory.memory_type}] {memory.content}\n"
            if total_len + len(line) > max_tokens:
                break
            context_lines.append(line)
            total_len += len(line)

        return "".join(context_lines)

    async def _cleanup_if_needed(self):
        """清理超出容量的记忆"""
        all_memories = []
        for memory_type in ["fact", "preference", "experience", "context"]:
            all_memories.extend(await self.store.list_by_type(memory_type, limit=1000))

        if len(all_memories) > self.max_memories:
            all_memories.sort(key=lambda m: m.importance + m.access_count * 0.2)
            excess = all_memories[:len(all_memories) - self.max_memories]
            for memory in excess:
                memory_id = memory.content[:32] + str(memory.timestamp.timestamp())
                await self.store.delete(memory_id)

    async def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        stats = {"total": 0, "by_type": {}, "avg_importance": 0.0}
        type_counts: Dict[str, int] = {}
        total_importance = 0.0

        for memory_type in ["fact", "preference", "experience", "context"]:
            memories = await self.store.list_by_type(memory_type, limit=1000)
            type_counts[memory_type] = len(memories)
            stats["total"] += len(memories)
            total_importance += sum(m.importance for m in memories)

        stats["by_type"] = type_counts
        if stats["total"] > 0:
            stats["avg_importance"] = total_importance / stats["total"]

        return stats
