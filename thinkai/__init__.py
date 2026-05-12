"""
ThinkAi - Enterprise-grade AI Framework
基于Python异步的企业级AI大模型集成框架
开箱即用,支持多模型,RAG,Agent,Skill等核心能力
"""

__version__ = "0.3.0"
__author__ = "ThinkAi Team"

from thinkai.core.client import ThinkAI
from thinkai.core.config import Settings
from thinkai.session.manager import SessionManager
from thinkai.prompt.template import PromptTemplate
from thinkai.rag.pipeline import RAGPipeline
from thinkai.agent.base import Agent
from thinkai.agent.react import ReActAgent
from thinkai.agent.function_calling import FunctionCallingAgent
from thinkai.agent.tool import Tool, tool
from thinkai.skill import Skill, SkillManager, skill_manager
from thinkai.skill import WebSearchSkill, CodeSkill, MathSkill, FileSkill

__all__ = [
    "ThinkAI",
    "Settings",
    "SessionManager",
    "PromptTemplate",
    "RAGPipeline",
    "Agent",
    "ReActAgent",
    "FunctionCallingAgent",
    "Tool",
    "tool",
    "Skill",
    "SkillManager",
    "skill_manager",
    "WebSearchSkill",
    "CodeSkill",
    "MathSkill",
    "FileSkill",
]
