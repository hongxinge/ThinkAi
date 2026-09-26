"""Redis存储实现 - 生产环境会话持久化"""
import json
from typing import Optional, List, Dict, Any

from thinkai.session.storage import BaseStorage


class RedisStorage(BaseStorage):
    """
    Redis会话存储

    适用于生产环境和多实例部署。依赖 redis 库:
        pip install "redis>=4.2"

    使用示例:
        storage = RedisStorage(url="redis://127.0.0.1:6379/0")
        manager = SessionManager(config)
        manager.storage = storage
    """

    def __init__(
        self,
        url: Optional[str] = None,
        prefix: str = "thinkai:session:",
    ):
        try:
            import redis.asyncio as aioredis
        except ImportError as e:
            raise ImportError(
                "Redis存储需要 redis 库支持,请安装: pip install 'redis>=4.2'"
            ) from e

        if not url:
            from thinkai.exceptions import ConfigurationError
            raise ConfigurationError(
                "使用Redis会话存储必须配置连接地址, "
                '例如 SessionConfig(storage="redis", redis_url="redis://127.0.0.1:6379/0") '
                "或设置环境变量 THINKAI_SESSION_REDIS_URL"
            )
        if not str(url).startswith(("redis://", "rediss://", "unix://")):
            from thinkai.exceptions import ConfigurationError
            raise ConfigurationError(
                f"无效的Redis连接地址: '{url}', "
                "必须以 redis:// 、rediss:// 或 unix:// 开头"
            )

        self._redis = aioredis.from_url(url, decode_responses=True)
        self.prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    async def get(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取会话消息"""
        data = await self._redis.get(self._key(session_id))
        if data is None:
            return None
        return json.loads(data)

    async def set(self, session_id: str, messages: List[Dict[str, Any]], ttl: int = 3600):
        """保存会话消息"""
        await self._redis.set(
            self._key(session_id),
            json.dumps(messages, ensure_ascii=False),
            ex=ttl,
        )

    async def delete(self, session_id: str):
        """删除会话"""
        await self._redis.delete(self._key(session_id))

    async def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return bool(await self._redis.exists(self._key(session_id)))

    async def clear(self):
        """清空本框架前缀的所有会话(不触碰其他业务的键)"""
        keys = []
        async for key in self._redis.scan_iter(match=f"{self.prefix}*"):
            keys.append(key)
        if keys:
            await self._redis.delete(*keys)

    async def close(self):
        """关闭Redis连接"""
        close = getattr(self._redis, "aclose", None) or getattr(self._redis, "close", None)
        if close:
            await close()
