"""Gemini Provider - Google Gemini API"""
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


@register_provider("gemini")
class GeminiProvider(BaseProvider):
    """
    Google Gemini Provider
    
    API文档: https://ai.google.dev/gemini-api/docs
    """

    name = "gemini"
    default_model = "gemini-pro"
    default_api_base = "https://generativelanguage.googleapis.com/v1beta"

    def _get_headers(self) -> Dict[str, str]:
        """Gemini API请求头"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "ThinkAi/0.1.0",
        }

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        client = await self._get_client()
        model = (request.model or self.model).split("/")[-1]
        endpoint = f"/models/{model}:generateContent?key={self.api_key}"
        
        payload = self._build_chat_request_payload(request)

        response = await client.post(endpoint, json=payload)

        if response.status_code != 200:
            await self._handle_api_error(response)

        data = response.json()
        return self._parse_response(data)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """流式聊天接口"""
        client = await self._get_client()
        model = (request.model or self.model).split("/")[-1]
        endpoint = f"/models/{model}:streamGenerateContent?key={self.api_key}"
        
        payload = self._build_chat_request_payload(request)

        async with client.stream("POST", endpoint, json=payload) as response:
            if response.status_code != 200:
                await self._handle_api_error(response)

            buffer = ""
            async for chunk_text in response.aiter_text():
                buffer += chunk_text
                
                while True:
                    newline_idx = buffer.find("\n")
                    if newline_idx == -1:
                        break
                    
                    line = buffer[:newline_idx].strip()
                    buffer = buffer[newline_idx + 1:]
                    
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        yield self._parse_stream_chunk(data)
                    except json.JSONDecodeError:
                        continue

    def _build_chat_request_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """构建Gemini API请求"""
        contents = []
        for msg in request.messages:
            role = "model" if msg.role == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        generation_config = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens or 2048,
        }

        if request.top_p:
            generation_config["topP"] = request.top_p
        if request.stop:
            stop_sequences = request.stop if isinstance(request.stop, list) else [request.stop]
            generation_config["stopSequences"] = stop_sequences

        payload = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        return payload

    def _parse_response(self, data: Dict[str, Any]) -> ChatResponse:
        """解析Gemini响应"""
        candidates = data.get("candidates", [])
        content_text = ""
        finish_reason = None

        if candidates:
            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])
            for part in content_parts:
                content_text += part.get("text", "")
            finish_reason = candidate.get("finishReason")

        usage_metadata = data.get("usageMetadata", {})

        return ChatResponse(
            id="",
            model=self.model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=content_text,
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=usage_metadata.get("promptTokenCount", 0),
                completion_tokens=usage_metadata.get("candidatesTokenCount", 0),
                total_tokens=usage_metadata.get("totalTokenCount", 0),
            ),
        )

    def _parse_stream_chunk(self, data: Dict[str, Any]) -> StreamChunk:
        """解析Gemini流式响应"""
        candidates = data.get("candidates", [])
        content_text = ""
        finish_reason = None

        if candidates:
            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])
            for part in content_parts:
                content_text += part.get("text", "")
            finish_reason = candidate.get("finishReason")

        return StreamChunk(
            id="",
            model=self.model,
            choices=[
                StreamChoice(
                    index=0,
                    delta=ChatMessage(
                        role="assistant",
                        content=content_text,
                    ),
                    finish_reason=finish_reason,
                )
            ],
        )
