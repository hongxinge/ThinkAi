"""Provider模块"""
from thinkai.providers.base import BaseProvider, ProviderFactory
from thinkai.providers.registry import ProviderRegistry, registry
from thinkai.providers.ollama import OllamaProvider
from thinkai.providers.openai import OpenAIProvider
from thinkai.providers.qwen import QwenProvider
from thinkai.providers.deepseek import DeepSeekProvider
from thinkai.providers.openai_compatible import OpenAICompatibleProvider
from thinkai.providers.claude import ClaudeProvider
from thinkai.providers.gemini import GeminiProvider

import thinkai.providers.shortcuts

__all__ = [
    "BaseProvider",
    "ProviderFactory",
    "ProviderRegistry",
    "registry",
    "OllamaProvider",
    "OpenAIProvider",
    "QwenProvider",
    "DeepSeekProvider",
    "OpenAICompatibleProvider",
    "ClaudeProvider",
    "GeminiProvider",
]
