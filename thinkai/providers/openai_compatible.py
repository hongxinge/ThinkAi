"""OpenAI兼容Provider - 统一处理所有兼容OpenAI API的模型"""
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


@register_provider("openai-compatible")
class OpenAICompatibleProvider(BaseProvider):
    """
    OpenAI兼容Provider - 统一处理所有兼容OpenAI API格式的模型
    
    支持的模型(通过配置预设):
    - DeepSeek: deepseek-chat, deepseek-coder
    - 通义千问: qwen-turbo, qwen-plus, qwen-max
    - 智谱GLM: glm-4, glm-3-turbo
    - 百度文心: ernie-bot, ernie-bot-turbo
    - 腾讯混元: hunyuan
    - 豆包ARK: doubao-pro, doubao-lite
    - Kimi: moonshot-v1-8k, moonshot-v1-32k
    - MiniMax: abab6-chat
    """

    name = "openai-compatible"
    
    # Provider预设配置 - 开箱即用
    PRESETS: Dict[str, Dict[str, Any]] = {
        "openai": {
            "api_base": "https://api.openai.com/v1",
            "default_model": "gpt-3.5-turbo",
        },
        "deepseek": {
            "api_base": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
        },
        "qwen": {
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-turbo",
        },
        "glm": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-4",
        },
        "baidu": {
            "api_base": "https://qianfan.baidubce.com/v2",
            "default_model": "ernie-bot",
        },
        "tencent": {
            "api_base": "https://api.hunyuan.cloud.tencent.com/v1",
            "default_model": "hunyuan",
        },
        "doubao": {
            "api_base": "https://ark.cn-beijing.volces.com/api/v3",
            "default_model": "doubao-pro",
        },
        "kimi": {
            "api_base": "https://api.moonshot.cn/v1",
            "default_model": "moonshot-v1-8k",
        },
        "minimax": {
            "api_base": "https://api.minimax.chat/v1",
            "default_model": "abab6-chat",
        },
    }

    def __init__(
        self,
        api_key: str,
        api_base: str = None,
        model: str = None,
        provider_preset: str = None,
        **kwargs,
    ):
        # 如果指定了provider预设名称,自动加载配置
        if provider_preset and provider_preset in self.PRESETS:
            preset = self.PRESETS[provider_preset]
            api_base = api_base or preset["api_base"]
            model = model or preset["default_model"]
        
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            model=model,
            **kwargs,
        )

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
        """解析OpenAI格式响应"""
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
