"""Plugin系统 - 动态加载外部Skill、Provider和Middleware"""
import importlib
import pkgutil
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


class PluginInfo(BaseModel):
    """插件元信息"""

    name: str
    version: str
    description: str
    author: str = ""
    plugin_type: str
    entry_point: str
    dependencies: List[str] = []

    @field_validator("plugin_type")
    @classmethod
    def validate_plugin_type(cls, v: str) -> str:
        allowed = {"skill", "provider", "middleware", "multi"}
        if v not in allowed:
            raise ValueError(f"plugin_type must be one of {allowed}, got '{v}'")
        return v


class PluginManager:
    """
    Plugin管理器 - 注册、加载和管理插件

    支持动态加载外部Skill、Provider和Middleware,
    通过entry_point格式 "module_path:class_name" 导入并实例化。
    """

    def __init__(self):
        self._registry: Dict[str, PluginInfo] = {}
        self._loaded: Dict[str, Any] = {}

    def register(self, plugin_info: PluginInfo) -> None:
        """注册插件"""
        if plugin_info.name in self._registry:
            logger.warning("Plugin '%s' already registered, overwriting", plugin_info.name)
        self._registry[plugin_info.name] = plugin_info
        logger.info("Registered plugin: %s v%s (%s)", plugin_info.name, plugin_info.version, plugin_info.plugin_type)

    def load(self, name: str) -> Any:
        """加载并返回插件实例,使用缓存"""
        if name in self._loaded:
            return self._loaded[name]
        if name not in self._registry:
            raise ValueError(f"Plugin '{name}' is not registered. Available: {list(self._registry.keys())}")
        plugin_info = self._registry[name]
        instance = self.load_from_entrypoint(plugin_info.entry_point)
        self._loaded[name] = instance
        logger.info("Loaded plugin: %s", name)
        return instance

    def unload(self, name: str) -> None:
        """卸载插件,移除缓存实例"""
        if name in self._loaded:
            del self._loaded[name]
            logger.info("Unloaded plugin: %s", name)
        else:
            logger.warning("Plugin '%s' is not loaded, nothing to unload", name)

    def list_plugins(self) -> List[PluginInfo]:
        """列出所有已注册插件"""
        return list(self._registry.values())

    def is_loaded(self, name: str) -> bool:
        """检查插件是否已加载"""
        return name in self._loaded

    def load_from_entrypoint(self, entry_point: str) -> Any:
        """
        从entry_point字符串加载并实例化类

        entry_point格式: "module_path:class_name"
        例如: "my_package.my_module:MySkill"

        Args:
            entry_point: 模块路径和类名,以冒号分隔

        Returns:
            实例化后的对象

        Raises:
            ValueError: entry_point格式不正确
            ImportError: 模块无法导入
            AttributeError: 类在模块中不存在
        """
        if ":" not in entry_point:
            raise ValueError(
                f"Invalid entry_point format: '{entry_point}'. Expected 'module_path:class_name'"
            )
        module_path, class_name = entry_point.rsplit(":", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()

    def auto_discover(self, package_name: str = "thinkai_plugins") -> List[PluginInfo]:
        """
        从包命名空间自动发现并注册插件

        扫描指定包下所有模块,查找带有 _thinkai_plugin_info 属性的类,
        自动注册为插件。

        Args:
            package_name: 要扫描的包名,默认 "thinkai_plugins"

        Returns:
            新发现的插件信息列表
        """
        discovered: List[PluginInfo] = []
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.info("Plugin package '%s' not found, skipping auto-discovery", package_name)
            return discovered

        package_path = getattr(package, "__path__", None)
        if package_path is None:
            logger.warning("Package '%s' has no __path__, cannot discover plugins", package_name)
            return discovered

        for importer, module_name, is_pkg in pkgutil.iter_modules(package_path, prefix=f"{package_name}."):
            if is_pkg:
                continue
            try:
                module = importlib.import_module(module_name)
                plugin_info_attr = getattr(module, "_thinkai_plugin_info", None)
                if plugin_info_attr is not None:
                    if isinstance(plugin_info_attr, PluginInfo):
                        self.register(plugin_info_attr)
                        discovered.append(plugin_info_attr)
                    elif isinstance(plugin_info_attr, list):
                        for info in plugin_info_attr:
                            if isinstance(info, PluginInfo):
                                self.register(info)
                                discovered.append(info)
            except Exception as e:
                logger.error("Failed to discover plugin in '%s': %s", module_name, e)

        logger.info("Auto-discovered %d plugin(s) from '%s'", len(discovered), package_name)
        return discovered

    def install_skill(self, plugin_name: str, skill_manager: Any) -> Any:
        """
        将插件作为Skill安装到SkillManager

        Args:
            plugin_name: 已注册的插件名称
            skill_manager: SkillManager实例

        Returns:
            加载的Skill实例
        """
        from thinkai.skill import Skill

        instance = self.load(plugin_name)
        if not isinstance(instance, Skill):
            raise TypeError(
                f"Plugin '{plugin_name}' is not a Skill instance, got {type(instance).__name__}"
            )
        skill_manager.register(instance)
        logger.info("Installed plugin '%s' as Skill", plugin_name)
        return instance

    def install_provider(self, plugin_name: str, registry: Any) -> Any:
        """
        将插件作为Provider安装到ProviderRegistry

        Args:
            plugin_name: 已注册的插件名称
            registry: ProviderRegistry实例

        Returns:
            加载的Provider类
        """
        from thinkai.providers.base import BaseProvider

        instance = self.load(plugin_name)
        if not isinstance(instance, type) or not issubclass(instance, BaseProvider):
            raise TypeError(
                f"Plugin '{plugin_name}' is not a BaseProvider subclass, got {type(instance).__name__}"
            )
        registry.register(plugin_name, instance)
        logger.info("Installed plugin '%s' as Provider", plugin_name)
        return instance

    def install_middleware(self, plugin_name: str, ai_client: Any) -> Any:
        """
        将插件作为Middleware安装到ThinkAI客户端

        Args:
            plugin_name: 已注册的插件名称
            ai_client: ThinkAI客户端实例

        Returns:
            加载的Middleware实例
        """
        from thinkai.middleware.base import BaseMiddleware

        instance = self.load(plugin_name)
        if not isinstance(instance, BaseMiddleware):
            raise TypeError(
                f"Plugin '{plugin_name}' is not a BaseMiddleware instance, got {type(instance).__name__}"
            )
        if hasattr(ai_client, "add_middleware"):
            ai_client.add_middleware(instance)
        else:
            raise AttributeError("ai_client does not have an 'add_middleware' method")
        logger.info("Installed plugin '%s' as Middleware", plugin_name)
        return instance


def thinkai_plugin(
    name: str,
    version: str,
    description: str,
    plugin_type: str,
    author: str = "",
    entry_point: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
):
    """
    插件类装饰器 - 声明类为ThinkAi插件

    使用示例:
        @thinkai_plugin(name="my-skill", version="1.0", description="My custom skill", plugin_type="skill")
        class MySkill(Skill):
            ...

    装饰后会自动在类上设置 _thinkai_plugin_info 属性,
    并注册到全局 plugin_manager。
    """

    def decorator(cls):
        ep = entry_point or f"{cls.__module__}:{cls.__qualname__}"
        info = PluginInfo(
            name=name,
            version=version,
            description=description,
            author=author,
            plugin_type=plugin_type,
            entry_point=ep,
            dependencies=dependencies or [],
        )
        cls._thinkai_plugin_info = info
        module = importlib.import_module(cls.__module__)
        if not hasattr(module, "_thinkai_plugin_info"):
            setattr(module, "_thinkai_plugin_info", info)
        else:
            existing = getattr(module, "_thinkai_plugin_info")
            if isinstance(existing, list):
                existing.append(info)
            else:
                setattr(module, "_thinkai_plugin_info", [existing, info])
        plugin_manager.register(info)
        return cls

    return decorator


plugin_manager = PluginManager()

__all__ = [
    "PluginInfo",
    "PluginManager",
    "plugin_manager",
    "thinkai_plugin",
]
