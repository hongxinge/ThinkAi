"""Provider快捷注册 - 为所有预设Provider创建快捷名称

设计约定：本模块在 thinkai.providers 包初始化的末尾执行，会用
OpenAICompatibleProvider 的预设子类覆盖同名注册表条目（openai、
qwen、deepseek 等）。也就是说这些 Provider 统一由 OpenAI 兼容层
提供服务，providers/openai.py、qwen.py、deepseek.py 中的独立实现
不再被默认路由命中。该行为由 tests/test_v080_regressions.py 的
注册表用例锁定，调整前须同步评估 Function Calling 兼容性。
"""
from thinkai.providers.registry import register_provider
from thinkai.providers.openai_compatible import OpenAICompatibleProvider
from thinkai.core.models import ChatMessage, Usage, ChatChoice, StreamChoice


# 为每个预设创建快捷Provider类(继承自OpenAICompatibleProvider)
def create_provider_class(provider_name: str, preset: dict):
    """动态创建Provider类"""
    
    @register_provider(provider_name)
    class QuickProvider(OpenAICompatibleProvider):
        __doc__ = f"{provider_name.upper()} Provider - 预设配置"
        name = provider_name
        default_model = preset["default_model"]
        default_api_base = preset["api_base"]

        def __init__(self, api_key: str = None, **kwargs):
            super().__init__(
                api_key=api_key,
                provider_preset=provider_name,
                **kwargs,
            )


# 为所有预设创建Provider
for _name, _preset in OpenAICompatibleProvider.PRESETS.items():
    create_provider_class(_name, _preset)
