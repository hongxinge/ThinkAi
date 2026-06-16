"""OpenAI Provider - 使用官方OpenAI Python SDK"""
from typing import AsyncIterator, List, Optional, Dict, Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from thinkai.providers.base import BaseProvider
from thinkai.providers.registry import register_provider
from thinkai.core.models import (
    ChatRequest,
    ChatResponse,
    StreamChunk,
    ChatMessage,
    ChatChoice,
    StreamChoice,
    Usage,
    ToolCall,
    FunctionCall,
)
from thinkai.exceptions import (
    APIError,
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
)


@register_provider("openai")
class OpenAIProvider(BaseProvider):
    """
    OpenAI Provider - 使用官方OpenAI Python SDK
    支持GPT-4、GPT-3.5等模型
    文档: https://platform.openai.com/docs/api-reference
    """

    name = "openai"
    default_model = "gpt-3.5-turbo"
    default_api_base = "https://api.openai.com/v1"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.api_base:
            self.api_base = self.default_api_base

        self._async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=float(self.timeout),
            max_retries=0,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload = self._build_chat_request_payload(request)
        payload.pop("stream", None)

        try:
            completion: ChatCompletion = await self._async_client.chat.completions.create(
                **payload,
            )
        except Exception as exc:
            self._map_sdk_exception(exc)

        return self._convert_chat_response(completion)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        payload = self._build_chat_request_payload(request)
        payload["stream"] = True

        try:
            stream = await self._async_client.chat.completions.create(**payload)
            async for chunk in stream:
                yield self._convert_stream_chunk(chunk)
        except Exception as exc:
            self._map_sdk_exception(exc)

    def _convert_chat_response(self, completion: ChatCompletion) -> ChatResponse:
        choices = []
        for choice in completion.choices:
            msg = choice.message
            tool_calls = None
            if msg.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type=tc.type or "function",
                        function=FunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in msg.tool_calls
                ]
            choices.append(
                ChatChoice(
                    index=choice.index,
                    message=ChatMessage(
                        role=msg.role,
                        content=msg.content,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=choice.finish_reason,
                )
            )

        usage = None
        if completion.usage:
            usage = Usage(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens,
            )

        return ChatResponse(
            id=completion.id,
            model=completion.model or self.model,
            choices=choices,
            usage=usage,
        )

    def _convert_stream_chunk(self, chunk: ChatCompletionChunk) -> StreamChunk:
        if not chunk.choices:
            return StreamChunk(
                id=chunk.id or "",
                model=chunk.model or self.model,
                choices=[],
            )

        choice_data = chunk.choices[0]
        delta = choice_data.delta

        tool_calls = None
        if delta.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id or "",
                    type=tc.type or "function",
                    function=FunctionCall(
                        name=tc.function.name or "",
                        arguments=tc.function.arguments or "",
                    ),
                )
                for tc in delta.tool_calls
            ]

        return StreamChunk(
            id=chunk.id or "",
            model=chunk.model or self.model,
            choices=[
                StreamChoice(
                    index=choice_data.index,
                    delta=ChatMessage(
                        role=delta.role or "assistant",
                        content=delta.content,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=choice_data.finish_reason,
                )
            ],
        )

    def _map_sdk_exception(self, exc: Exception) -> None:
        import openai

        if isinstance(exc, openai.AuthenticationError):
            raise AuthenticationError(self.name) from exc
        if isinstance(exc, openai.RateLimitError):
            raise RateLimitError(self.name) from exc
        if isinstance(exc, openai.APIConnectionError):
            raise APIConnectionError(str(exc), self.name) from exc
        if isinstance(exc, openai.APIStatusError):
            raise APIError(str(exc), self.name, exc.status_code) from exc
        if isinstance(exc, openai.APIError):
            raise APIError(str(exc), self.name) from exc

        raise

    async def close(self):
        if self._async_client is not None:
            await self._async_client.close()
        await super().close()