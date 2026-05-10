"""Claude Provider - Anthropic Claude API"""
from typing import AsyncIterator, Dict, Any
import httpx
import json

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
)
from thinkai.exceptions import APIError


@register_provider("claude")
class ClaudeProvider(BaseProvider):
    """
    Anthropic Claude Provider
    
    API文档: https://docs.anthropic.com/claude/reference/messages_post
    """

    name = "claude"
    default_model = "claude-3-5-sonnet-20241022"
    default_api_base = "https://api.anthropic.com/v1"

    def _get_headers(self) -> Dict[str, str]:
        """Claude API使用x-api-key认证"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "ThinkAi/0.1.0",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        client = await self._get_client()
        payload = self._build_chat_request_payload(request)

        response = await client.post("/messages", json=payload)

        if response.status_code != 200:
            await self._handle_api_error(response)

        data = response.json()
        return self._parse_response(data)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """流式聊天接口"""
        client = await self._get_client()
        payload = self._build_chat_request_payload(request)
        payload["stream"] = True

        async with client.stream("POST", "/messages", json=payload) as response:
            if response.status_code != 200:
                await self._handle_api_error(response)

            async for line in response.aiter_lines():
                if not line.strip():
                    continue

                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type")
                        if event_type == "content_block_delta":
                            yield self._parse_stream_chunk(data)
                    except json.JSONDecodeError:
                        continue

    def _build_chat_request_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """构建Claude API请求"""
        model = request.model or self.model
        if "/" in model:
            model = model.split("/")[-1]

        messages = []
        system_prompt = None
        
        for msg in request.messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                role = "assistant" if msg.role == "assistant" else "user"
                messages.append({"role": role, "content": msg.content})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt
        if request.top_p:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop_sequences"] = request.stop if isinstance(request.stop, list) else [request.stop]
        
        return payload

    def _parse_response(self, data: Dict[str, Any]) -> ChatResponse:
        """解析Claude响应"""
        content_text = ""
        for content in data.get("content", []):
            if content.get("type") == "text":
                content_text += content.get("text", "")

        return ChatResponse(
            id=data.get("id", ""),
            model=data.get("model", self.model),
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=content_text,
                    ),
                    finish_reason=data.get("stop_reason"),
                )
            ],
            usage=Usage(
                prompt_tokens=data.get("usage", {}).get("input_tokens", 0),
                completion_tokens=data.get("usage", {}).get("output_tokens", 0),
                total_tokens=(
                    data.get("usage", {}).get("input_tokens", 0)
                    + data.get("usage", {}).get("output_tokens", 0)
                ),
            ),
        )

    def _parse_stream_chunk(self, data: Dict[str, Any]) -> StreamChunk:
        """解析Claude流式响应"""
        delta = data.get("delta", {})
        text = delta.get("text", "")

        return StreamChunk(
            id=data.get("message_id", ""),
            model=self.model,
            choices=[
                StreamChoice(
                    index=0,
                    delta=ChatMessage(
                        role="assistant",
                        content=text,
                    ),
                    finish_reason=None,
                )
            ],
        )
