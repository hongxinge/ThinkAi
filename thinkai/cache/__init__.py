"""ThinkAI缓存层 - LRU缓存减少重复API调用"""
import asyncio
import functools
import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional

from thinkai.core.models import ChatRequest, ChatResponse
from thinkai.middleware.base import BaseMiddleware


class BaseCache(ABC):
    """缓存抽象基类"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    async def clear(self) -> None:
        pass


class MemoryCache(BaseCache):
    """基于内存的LRU缓存,支持TTL过期"""

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._store:
                return None
            entry = self._store[key]
            if entry["expires_at"] is not None and time.time() > entry["expires_at"]:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return entry["value"]

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires_at = time.time() + (ttl if ttl is not None else self.default_ttl)
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = {"value": value, "expires_at": expires_at}
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class FileCache(BaseCache):
    """基于文件的持久化缓存,支持TTL过期"""

    def __init__(self, cache_dir: str = "./thinkai_data/cache", default_ttl: float = 3600):
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()
        os.makedirs(self.cache_dir, exist_ok=True)

    def _key_to_path(self, key: str) -> str:
        safe_key = hashlib.sha256(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{safe_key}.json")

    async def get(self, key: str) -> Optional[Any]:
        path = self._key_to_path(key)
        async with self._lock:
            if not os.path.exists(path):
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                if entry["expires_at"] is not None and time.time() > entry["expires_at"]:
                    os.remove(path)
                    return None
                return entry["value"]
            except (json.JSONDecodeError, KeyError, OSError):
                return None

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        path = self._key_to_path(key)
        expires_at = time.time() + (ttl if ttl is not None else self.default_ttl)
        entry = {"value": value, "expires_at": expires_at}
        async with self._lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)

    async def delete(self, key: str) -> bool:
        path = self._key_to_path(key)
        async with self._lock:
            if os.path.exists(path):
                os.remove(path)
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.cache_dir, filename))


class CacheMiddleware(BaseMiddleware):
    """缓存中间件 - 集成缓存到ThinkAI请求管道"""

    def __init__(
        self,
        cache: Optional[BaseCache] = None,
        ttl: float = 3600,
        backend: str = "memory",
        **kwargs,
    ):
        self.cache = cache or create_cache(backend=backend, **kwargs)
        self.ttl = ttl

    @staticmethod
    def _make_cache_key(request: ChatRequest) -> str:
        parts = [
            request.model,
            json.dumps([m.to_dict() for m in request.messages], sort_keys=True, ensure_ascii=False),
            str(request.temperature),
        ]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def process_request(self, request: ChatRequest) -> ChatRequest:
        if request.stream:
            return request
        cache_key = self._make_cache_key(request)
        cached_value = await self.cache.get(cache_key)
        if cached_value is not None:
            request.extra["_cached_response"] = cached_value
            request.extra["_cache_hit"] = True
        else:
            request.extra["_cache_key"] = cache_key
        return request

    async def process_response(self, response: ChatResponse) -> ChatResponse:
        return response

    async def store_response(self, request: ChatRequest, response: ChatResponse) -> None:
        cache_key = request.extra.get("_cache_key")
        if cache_key is None or request.stream:
            return
        await self.cache.set(cache_key, response.model_dump(), ttl=self.ttl)

    @staticmethod
    def get_cached_response(request: ChatRequest) -> Optional[Dict[str, Any]]:
        return request.extra.get("_cached_response")

    @staticmethod
    def is_cache_hit(request: ChatRequest) -> bool:
        return request.extra.get("_cache_hit", False)


def cached(ttl: float = 3600, cache: Optional[BaseCache] = None):
    """异步函数缓存装饰器"""
    _cache = cache or MemoryCache(default_ttl=ttl)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key_parts = [func.__module__, func.__qualname__, repr(args), repr(kwargs)]
            cache_key = hashlib.sha256("|".join(key_parts).encode()).hexdigest()
            result = await _cache.get(cache_key)
            if result is not None:
                return result
            result = await func(*args, **kwargs)
            await _cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator


def create_cache(backend: str = "memory", **kwargs) -> BaseCache:
    """缓存工厂函数"""
    if backend == "memory":
        return MemoryCache(**kwargs)
    elif backend == "file":
        return FileCache(**kwargs)
    else:
        raise ValueError(f"不支持的缓存后端: {backend}, 可选: memory, file")


__all__ = [
    "BaseCache",
    "MemoryCache",
    "FileCache",
    "CacheMiddleware",
    "cached",
    "create_cache",
]
