"""
ThinkAi - Enterprise-grade AI Framework
基于FastAPI的企业级AI大模型集成框架
开箱即用,支持多模型,RAG,Agent等核心能力
"""

__version__ = "0.2.1"
__author__ = "ThinkAi Team"

from thinkai.core.client import ThinkAI
from thinkai.core.config import Settings
from thinkai.session.manager import SessionManager
from thinkai.prompt.template import PromptTemplate
from thinkai.rag.pipeline import RAGPipeline
from thinkai.agent.base import Agent

__all__ = [
    "ThinkAI",
    "Settings",
    "SessionManager",
    "PromptTemplate",
    "RAGPipeline",
    "Agent",
]
