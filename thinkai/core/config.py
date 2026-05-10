"""配置管理模块 - 支持环境变量、配置文件、多环境"""
import os
from pathlib import Path
from typing import Dict, Optional, Any, List
from pydantic import Field, model_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml
from dotenv import load_dotenv

from thinkai.exceptions import ConfigurationError


class ModelConfig(BaseSettings):
    """单个模型配置"""
    model_config = SettingsConfigDict(env_prefix="THINKAI_", extra="allow")
    
    provider: str = Field(default="ollama", description="Provider名称")
    model: str = Field(default="llama3", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    api_base: Optional[str] = Field(default=None, description="API基础URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    timeout: int = Field(default=60, description="超时时间(秒)")
    extra: Dict[str, Any] = Field(default_factory=dict, description="额外配置")


class ProviderConfig(BaseSettings):
    """Provider级别配置"""
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3
    extra: Dict[str, Any] = Field(default_factory=dict)


class SessionConfig(BaseSettings):
    """会话配置"""
    enabled: bool = True
    max_history: int = 20
    storage: str = "memory"
    ttl: int = 3600
    redis_url: Optional[str] = None


class RAGConfig(BaseSettings):
    """RAG配置"""
    enabled: bool = False
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5
    embedding_model: str = "nomic-embed-text"
    vector_store: str = "chroma"
    vector_store_path: str = "./thinkai_data/vectors"


class AgentConfig(BaseSettings):
    """Agent配置"""
    enabled: bool = False
    max_iterations: int = 10
    max_execution_time: int = 300
    verbose: bool = False


class Settings(BaseSettings):
    """全局配置 - 支持环境变量和配置文件"""
    model_config = SettingsConfigDict(
        env_prefix="THINKAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )
    
    app_name: str = Field(default="ThinkAi", description="应用名称")
    debug: bool = Field(default=False, description="调试模式")

    # 默认模型配置
    default_provider: str = Field(default="ollama", description="默认Provider")
    default_model: str = Field(default="llama3", description="默认模型")

    # Provider配置
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)

    # 模型配置映射
    models: Dict[str, ModelConfig] = Field(default_factory=dict)

    # 子模块配置
    session: SessionConfig = Field(default_factory=SessionConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

    # 日志配置
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = None

    # 配置文件路径
    config_file: Optional[str] = Field(default=None, description="配置文件路径")

    @model_validator(mode="before")
    @classmethod
    def load_config_file(cls, values):
        """加载配置文件"""
        config_file = values.get("config_file") or os.getenv("THINKAI_CONFIG_FILE")
        
        if config_file and Path(config_file).exists():
            with open(config_file, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f) or {}
            
            for key, value in file_config.items():
                if key not in values:
                    values[key] = value
        
        return values

    def get_model_config(self, name: Optional[str] = None) -> ModelConfig:
        """获取模型配置"""
        model_name = name or self.default_model
        
        if model_name not in self.models:
            return ModelConfig(
                provider=self.default_provider,
                model=model_name,
            )
        
        return self.models[model_name]

    def get_provider_config(self, provider: str) -> ProviderConfig:
        """获取Provider配置"""
        if provider not in self.providers:
            return ProviderConfig()
        return self.providers[provider]

    def register_model(self, name: str, config: Dict[str, Any]):
        """注册模型配置"""
        self.models[name] = ModelConfig(**config)

    def register_provider(self, name: str, config: Dict[str, Any]):
        """注册Provider配置"""
        self.providers[name] = ProviderConfig(**config)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump(exclude={"config_file"})

    @classmethod
    def from_file(cls, config_file: str) -> "Settings":
        """从文件创建配置"""
        return cls(config_file=config_file)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "Settings":
        """从字典创建配置"""
        return cls(**config_dict)
