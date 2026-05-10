"""Ollama Provider - 本地大模型支持"""
from typing import AsyncIterator, Optional, Dict, Any
import httpx
import json

from thinkai.providers.base import BaseProvider
from thinkai.providers.registry import register_provider
from thinkai.core.models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    StreamChunk,
    StreamChoice,
    Usage,
)
from thinkai.exceptions import APIError


@register_provider("ollama")
class OllamaProvider(BaseProvider):
    """
    Ollama Provider - 支持本地部署的大模型
    文档: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    name = "ollama"
    default_model = "llama3"
    default_api_base = "http://localhost:11434"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.api_base:
            self.api_base = self.default_api_base

    def _get_headers(self) -> Dict[str, str]:
        """Ollama不需要认证"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "ThinkAi/0.1.0",
        }

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        client = await self._get_client()
        
        payload = {
            "model": request.model or self.model,
            "messages": [msg.to_dict() for msg in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_predict": request.max_tokens or -1,
            }
        }
        
        if request.tools:
            payload["tools"] = [
                {
                    "type": tool.type,
                    "function": {
                        "name": tool.function.name,
                        "description": tool.function.description,
                        "parameters": tool.function.parameters,
                    }
                }
                for tool in request.tools
            ]
        
        response = await client.post("/api/chat", json=payload)
        
        if response.status_code != 200:
            await self._handle_api_error(response)
        
        data = response.json()
        return self._parse_response(data)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """流式聊天接口"""
        client = await self._get_client()
        
        payload = {
            "model": request.model or self.model,
            "messages": [msg.to_dict() for msg in request.messages],
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_predict": request.max_tokens or -1,
            }
        }
        
        import uuid
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        
        async with client.stream("POST", "/api/chat", json=payload) as response:
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                
                try:
                    data = json.loads(line)
                    yield self._parse_stream_chunk(data, chunk_id)
                except json.JSONDecodeError:
                    continue

    def _parse_response(self, data: Dict[str, Any]) -> ChatResponse:
        """解析Ollama响应"""
        message_data = data.get("message", {})
        
        return ChatResponse(
            id=f"chatcmpl-{hash(data.get('created_at', ''))}",
            model=data.get("model", self.model),
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role=message_data.get("role", "assistant"),
                        content=message_data.get("content"),
                    ),
                    finish_reason="stop" if data.get("done") else None,
                )
            ],
            usage=Usage(
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            ) if data.get("done") else None,
        )

    def _parse_stream_chunk(self, data: Dict[str, Any], chunk_id: str) -> StreamChunk:
        """解析流式响应块"""
        message_data = data.get("message", {})
        
        return StreamChunk(
            id=chunk_id,
            model=data.get("model", self.model),
            choices=[
                StreamChoice(
                    index=0,
                    delta=ChatMessage(
                        role=message_data.get("role", "assistant"),
                        content=message_data.get("content"),
                    ),
                    finish_reason="stop" if data.get("done") else None,
                )
            ],
        )
