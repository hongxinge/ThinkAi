"""Agent状态持久化 - 支持checkpoint/resume"""
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Agent执行状态"""

    agent_name: str
    agent_type: str
    status: str = "running"
    current_step: int = 0
    max_steps: int = 10
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> "AgentState":
        return cls.model_validate_json(data)


class StateStorage(ABC):
    """状态存储基类"""

    @abstractmethod
    async def save(self, state: AgentState) -> str:
        pass

    @abstractmethod
    async def load(self, state_id: str) -> AgentState:
        pass

    @abstractmethod
    async def delete(self, state_id: str):
        pass

    @abstractmethod
    async def list_states(self, agent_name: Optional[str] = None) -> List[AgentState]:
        pass


class FileStateStorage(StateStorage):
    """文件系统状态存储"""

    def __init__(self, storage_dir: str = "./thinkai_data/agent_states"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.storage_dir / "_index.json"
        self._index: Dict[str, Dict[str, str]] = self._load_index()

    def _load_index(self) -> Dict[str, Dict[str, str]]:
        if self._index_path.exists():
            with open(self._index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_index(self):
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def _state_path(self, state_id: str) -> Path:
        return self.storage_dir / f"{state_id}.json"

    async def save(self, state: AgentState) -> str:
        state_id = str(uuid.uuid4())
        state.updated_at = datetime.now()
        path = self._state_path(state_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(state.to_json())
        self._index[state_id] = {
            "agent_name": state.agent_name,
            "status": state.status,
            "file": str(path),
        }
        self._save_index()
        return state_id

    async def load(self, state_id: str) -> AgentState:
        path = self._state_path(state_id)
        if not path.exists():
            raise FileNotFoundError(f"State not found: {state_id}")
        with open(path, "r", encoding="utf-8") as f:
            return AgentState.from_json(f.read())

    async def delete(self, state_id: str):
        path = self._state_path(state_id)
        if path.exists():
            path.unlink()
        self._index.pop(state_id, None)
        self._save_index()

    async def list_states(self, agent_name: Optional[str] = None) -> List[AgentState]:
        states: List[AgentState] = []
        for state_id, info in self._index.items():
            if agent_name is not None and info.get("agent_name") != agent_name:
                continue
            path = self._state_path(state_id)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    states.append(AgentState.from_json(f.read()))
        return states


class MemoryStateStorage(StateStorage):
    """内存状态存储"""

    def __init__(self):
        self._states: Dict[str, AgentState] = {}

    async def save(self, state: AgentState) -> str:
        state_id = str(uuid.uuid4())
        state.updated_at = datetime.now()
        self._states[state_id] = state.model_copy(deep=True)
        return state_id

    async def load(self, state_id: str) -> AgentState:
        if state_id not in self._states:
            raise FileNotFoundError(f"State not found: {state_id}")
        return self._states[state_id].model_copy(deep=True)

    async def delete(self, state_id: str):
        self._states.pop(state_id, None)

    async def list_states(self, agent_name: Optional[str] = None) -> List[AgentState]:
        if agent_name is not None:
            return [s.model_copy(deep=True) for s in self._states.values() if s.agent_name == agent_name]
        return [s.model_copy(deep=True) for s in self._states.values()]


class PersistentAgentMixin:
    """为Agent添加状态持久化能力"""

    _state: Optional[AgentState] = None

    def _get_agent_type(self) -> str:
        cls_name = self.__class__.__name__.lower()
        for keyword in ("react", "function_calling", "streaming_fc"):
            if keyword in cls_name:
                return keyword
        return "unknown"

    def _build_state(self) -> AgentState:
        return AgentState(
            agent_name=getattr(self, "name", "agent"),
            agent_type=self._get_agent_type(),
            status="running",
            current_step=getattr(self, "_current_step", 0),
            max_steps=getattr(self, "max_iterations", 10),
            messages=getattr(self, "_messages", []),
            tool_results=getattr(self, "_tool_results", []),
            metadata=getattr(self, "extra", {}),
        )

    def _apply_state(self, state: AgentState):
        self._state = state
        if hasattr(self, "_messages"):
            self._messages = state.messages
        if hasattr(self, "_tool_results"):
            self._tool_results = state.tool_results
        if hasattr(self, "_current_step"):
            self._current_step = state.current_step

    async def save_state(self, storage: StateStorage) -> str:
        state = self._state or self._build_state()
        state.updated_at = datetime.now()
        self._state = state
        return await storage.save(state)

    async def restore_state(self, state_id: str, storage: StateStorage):
        state = await storage.load(state_id)
        self._apply_state(state)

    async def pause(self, storage: StateStorage) -> str:
        state = self._state or self._build_state()
        state.status = "paused"
        state.updated_at = datetime.now()
        self._state = state
        return await storage.save(state)

    async def resume(self, state_id: str, storage: StateStorage):
        state = await storage.load(state_id)
        state.status = "running"
        state.updated_at = datetime.now()
        self._apply_state(state)
        self._state = state


def create_state_storage(backend: str = "file", **kwargs) -> StateStorage:
    """创建状态存储实例"""
    if backend == "file":
        return FileStateStorage(**kwargs)
    if backend == "memory":
        return MemoryStateStorage()
    raise ValueError(f"Unknown storage backend: {backend}")
