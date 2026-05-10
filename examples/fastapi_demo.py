"""
ThinkAi 示例 - FastAPI集成
"""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from thinkai import ThinkAI
from thinkai.rag import RAGPipeline
from thinkai.agent import ReActAgent, Tool

app = FastAPI(title="ThinkAi Demo")

ai = ThinkAI(provider="ollama", model="llama3")


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    model: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """基础聊天接口"""
    response = await ai.chat(
        messages=request.message,
        model=request.model,
        session_id=request.session_id,
    )
    return ChatResponse(
        content=response.content or "",
        model=response.model,
    )


@app.get("/models")
async def list_models():
    """列出可用模型"""
    return ai.list_models()


@app.post("/complete")
async def complete(message: str, model: Optional[str] = None):
    """简化聊天接口"""
    content = await ai.complete(message, model=model)
    return {"content": content}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
