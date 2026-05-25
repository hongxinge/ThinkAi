"""同步API封装 - 为简单脚本提供同步接口"""
import asyncio
from typing import Optional, List, Union
from thinkai.core.client import ThinkAI
from thinkai.core.models import ChatResponse, ChatMessage


def _run_async(coro):
    """运行异步协程的辅助函数"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class SyncThinkAI:
    """
    ThinkAI同步客户端 - 简单脚本无需async/await

    使用示例:
        from thinkai.sync import SyncThinkAI

        ai = SyncThinkAI(provider="ollama", model="llama3")
        response = ai.chat("你好")
        print(response.content)
    """

    def __init__(self, **kwargs):
        self._async_client = ThinkAI(**kwargs)

    def chat(self, messages, **kwargs) -> ChatResponse:
        return _run_async(self._async_client.chat(messages, **kwargs))

    def complete(self, messages, **kwargs) -> str:
        return _run_async(self._async_client.complete(messages, **kwargs))

    def register_model(self, name, **kwargs):
        self._async_client.register_model(name, **kwargs)

    def register_provider(self, name, provider_class, **kwargs):
        self._async_client.register_provider(name, provider_class, **kwargs)

    def add_middleware(self, middleware):
        self._async_client.add_middleware(middleware)

    def switch_provider(self, provider, model=None):
        return _run_async(self._async_client.switch_provider(provider, model))

    def list_providers(self):
        return self._async_client.list_providers()

    def list_models(self):
        return self._async_client.list_models()

    def close(self):
        return _run_async(self._async_client.close())

    def __repr__(self):
        return repr(self._async_client)
