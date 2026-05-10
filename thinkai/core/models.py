"""数据模型定义 - 符合OpenAI标准"""
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class FunctionCall(BaseModel):
    """函数调用"""
    name: str
    arguments: str


class ToolCall(BaseModel):
    """工具调用 - OpenAI兼容格式"""
    id: str
    type: str = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    """聊天消息 - OpenAI兼容格式"""
    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = {"role": self.role.value}
        if self.content is not None:
            data["content"] = self.content
        if self.name:
            data["name"] = self.name
        if self.function_call:
            data["function_call"] = self.function_call.model_dump()
        if self.tool_calls:
            data["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        """创建系统消息"""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        """创建用户消息"""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: Optional[str] = None, tool_calls: Optional[List[ToolCall]] = None) -> "ChatMessage":
        """创建助手消息"""
        return cls(role=MessageRole.ASSISTANT, content=content, tool_calls=tool_calls)

    @classmethod
    def function(cls, content: str, name: str) -> "ChatMessage":
        """创建函数结果消息"""
        return cls(role=MessageRole.FUNCTION, content=content, name=name)


class Tool(BaseModel):
    """工具定义 - OpenAI兼容格式"""
    type: str = "function"
    function: "FunctionDefinition"


class FunctionDefinition(BaseModel):
    """函数定义"""
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]


class ChatRequest(BaseModel):
    """聊天请求 - OpenAI兼容格式"""
    model: str = Field(default="llama3", description="模型名称")
    messages: List[ChatMessage] = Field(description="消息列表")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    n: int = Field(default=1, ge=1)
    stream: bool = Field(default=False, description="是否流式响应")
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = Field(default=None, gt=0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    user: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    """Token使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "Usage":
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )


class ChatChoice(BaseModel):
    """聊天选择结果"""
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "message": self.message.to_dict(),
            "finish_reason": self.finish_reason,
        }


class StreamChunk(BaseModel):
    """流式响应块"""
    id: str
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: List["StreamChoice"]
    usage: Optional[Usage] = None


class StreamChoice(BaseModel):
    """流式选择结果"""
    index: int = 0
    delta: ChatMessage
    finish_reason: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应 - OpenAI兼容格式"""
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: List[ChatChoice]
    usage: Optional[Usage] = None
    
    @property
    def message(self) -> ChatMessage:
        """获取第一条消息"""
        if self.choices:
            return self.choices[0].message
        raise ValueError("No choices in response")

    @property
    def content(self) -> Optional[str]:
        """获取响应内容"""
        return self.message.content

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [choice.to_dict() for choice in self.choices],
            "usage": self.usage.model_dump() if self.usage else None,
        }
