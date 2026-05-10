"""DeepSeek Provider - DeepSeek大模型支持"""
from typing import AsyncIterator, Optional, Dict, Any
import httpx
import json

from thinkai.providers.base import BaseProvider
from thinkai.providers.registry import register_provider
from thinkai.core.models import (
    ChatRequest,
    ChatResponse,
    StreamChunk,
)
from thinkai.exceptions import APIError


@register_provider("deepseek")
class DeepSeekProvider(BaseProvider):
    """
    DeepSeek Provider - 深度求索大模型
    文档: https://platform.deepseek.com/api-docs/
    注意: DeepSeek使用OpenAI兼容的API格式
    """

    name = "deepseek"
    default_model = "deepseek-chat"
    default_api_base = "https://api.deepseek.com/v1"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.api_base:
            self.api_base = self.default_api_base

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        client = await self._get_client()
        payload = self._build_chat_request_payload(request)
        
        response = await client.post("/chat/completions", json=payload)
        
        if response.status_code != 200:
            await self._handle_api_error(response)
        
        data = response.json()
        return self._parse_response(data)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """流式聊天接口"""
        client = await self._get_client()
        payload = self._build_chat_request_payload(request)
        payload["stream"] = True
        
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                
                if line.startswith("data: "):
                    data_str = line[6:]
                    
                    if data_str.strip() == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        yield self._parse_stream_chunk(data)
                    except json.JSONDecodeError:
                        continue

    def _parse_response(self, data: Dict[str, Any]) -> ChatResponse:
        """解析DeepSeek响应"""
        return ChatResponse(
            id=data.get("id", ""),
            model=data.get("model", self.model),
            choices=[
                ChatChoice(
                    index=choice.get("index", 0),
                    message=ChatMessage(
                        role=choice["message"]["role"],
                        content=choice["message"].get("content"),
                    ),
                    finish_reason=choice.get("finish_reason"),
                )
                for choice in data.get("choices", [])
            ],
            usage=Usage.from_dict(data.get("usage", {})),
        )

    def _parse_stream_chunk(self, data: Dict[str, Any]) -> StreamChunk:
        """解析流式响应块"""
        choice_data = data.get("choices", [{}])[0]
        delta = choice_data.get("delta", {})
        
        return StreamChunk(
            id=data.get("id", ""),
            model=data.get("model", self.model),
            choices=[
                StreamChoice(
                    index=choice_data.get("index", 0),
                    delta=ChatMessage(
                        role=delta.get("role", "assistant"),
                        content=delta.get("content"),
                    ),
                    finish_reason=choice_data.get("finish_reason"),
                )
            ],
        )
