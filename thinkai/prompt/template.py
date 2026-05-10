"""Prompt模板模块"""
from typing import Dict, Optional, List, Any
from string import Template
import json
from thinkai.exceptions import PromptError


class PromptTemplate:
    """
    Prompt模板类
    支持变量替换和模板组合
    """

    def __init__(self, template: str, variables: Optional[Dict[str, str]] = None):
        self.template = template
        self.variables = variables or {}
        self._template = Template(template)

    def format(self, **kwargs) -> str:
        """格式化模板"""
        vars = {**self.variables, **kwargs}
        
        try:
            return self._template.substitute(vars)
        except KeyError as e:
            raise PromptError(f"Missing variable: {e}")

    @classmethod
    def from_file(cls, file_path: str, **kwargs):
        """从文件加载模板"""
        with open(file_path, "r", encoding="utf-8") as f:
            template = f.read()
        return cls(template, **kwargs)

    def __repr__(self) -> str:
        return f"PromptTemplate(template='{self.template[:50]}...')"


class PromptManager:
    """
    Prompt模板管理器
    """

    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(self, name: str, template: str, category: str = "default"):
        """注册模板"""
        self._templates[name] = PromptTemplate(template)
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)

    def register_template(self, name: str, template: PromptTemplate, category: str = "default"):
        """注册PromptTemplate对象"""
        self._templates[name] = template
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)

    def get(self, name: str) -> PromptTemplate:
        """获取模板"""
        if name not in self._templates:
            raise PromptError(f"Template '{name}' not found")
        return self._templates[name]

    def format(self, name: str, **kwargs) -> str:
        """格式化模板"""
        template = self.get(name)
        return template.format(**kwargs)

    def list_templates(self, category: Optional[str] = None) -> List[str]:
        """列出模板"""
        if category:
            return self._categories.get(category, [])
        return list(self._templates.keys())

    def list_categories(self) -> List[str]:
        """列出所有分类"""
        return list(self._categories.keys())

    def remove(self, name: str):
        """移除模板"""
        if name in self._templates:
            del self._templates[name]


# 内置模板
prompt_manager = PromptManager()

# 系统提示模板
prompt_manager.register(
    "system_default",
    "You are a helpful AI assistant. Provide clear, accurate, and concise responses.",
    category="system",
)

prompt_manager.register(
    "system_code",
    "You are an expert programmer. Write clean, efficient, and well-documented code.",
    category="system",
)

prompt_manager.register(
    "system_translation",
    "You are a professional translator. Translate the following text to $target_language:",
    category="system",
)

# RAG模板
prompt_manager.register(
    "rag_query",
    """Based on the following context, answer the question.
Context:
$context

Question: $question

Answer:""",
    category="rag",
)

prompt_manager.register(
    "rag_summarize",
    """Summarize the following text:
$text

Summary:""",
    category="rag",
)

# Agent模板
prompt_manager.register(
    "agent_react",
    """You are an AI assistant that can use tools to complete tasks.

Available tools:
$tools

Current task: $task

Think step by step and use tools when needed.""",
    category="agent",
)
