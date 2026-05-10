"""流式响应处理模块"""
from typing import AsyncIterator, Callable
from thinkai.core.models import StreamChunk


class StreamHandler:
    """流式响应处理器"""

    @staticmethod
    async def to_string(chunks: AsyncIterator[StreamChunk]) -> str:
        """将流式响应转换为完整字符串"""
        content = []
        async for chunk in chunks:
            if chunk.choices and chunk.choices[0].delta.content:
                content.append(chunk.choices[0].delta.content)
        return "".join(content)

    @staticmethod
    async def with_callback(
        chunks: AsyncIterator[StreamChunk],
        callback: Callable[[str], None],
    ) -> str:
        """流式响应并调用回调"""
        content = []
        async for chunk in chunks:
            if chunk.choices and chunk.choices[0].delta.content:
                delta = chunk.choices[0].delta.content
                content.append(delta)
                callback(delta)
        return "".join(content)

    @staticmethod
    async def sse_format(chunks: AsyncIterator[StreamChunk]) -> AsyncIterator[str]:
        """转换为SSE格式,适用于FastAPI StreamingResponse"""
        async for chunk in chunks:
            yield f"data: {chunk.model_dump_json()}\n\n"
