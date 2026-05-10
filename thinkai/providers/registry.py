"""Provider注册表 - 管理所有可用的Provider"""
from typing import Dict, Type, Optional
from thinkai.providers.base import BaseProvider


class ProviderRegistry:
    """
    Provider注册表
    支持动态注册和获取Provider
    """

    def __init__(self):
        self.providers: Dict[str, Type[BaseProvider]] = {}

    def register(self, name: str, provider_class: Type[BaseProvider]):
        """注册Provider"""
        if not issubclass(provider_class, BaseProvider):
            raise ValueError(f"Provider must inherit from BaseProvider, got {provider_class}")
        
        self.providers[name] = provider_class

    def get(self, name: str) -> Optional[Type[BaseProvider]]:
        """获取Provider类"""
        return self.providers.get(name)

    def list(self) -> Dict[str, Type[BaseProvider]]:
        """列出所有已注册的Provider"""
        return self.providers.copy()

    def is_available(self, name: str) -> bool:
        """检查Provider是否可用"""
        return name in self.providers

    def unregister(self, name: str):
        """注销Provider"""
        if name in self.providers:
            del self.providers[name]


# 全局注册表实例
registry = ProviderRegistry()


def register_provider(name: str):
    """
    Provider注册装饰器
    使用方式:
        @register_provider("ollama")
        class OllamaProvider(BaseProvider):
            ...
    """
    def decorator(provider_class: Type[BaseProvider]):
        registry.register(name, provider_class)
        return provider_class
    
    return decorator
