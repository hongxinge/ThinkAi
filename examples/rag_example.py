"""
ThinkAi 示例 - RAG使用
"""
import asyncio
from thinkai import ThinkAI
from thinkai.rag import RAGPipeline


async def example_rag():
    """RAG示例"""
    print("=" * 50)
    print("示例: RAG查询")
    print("=" * 50)
    
    ai = ThinkAI(provider="ollama", model="llama3")
    
    rag = RAGPipeline(
        documents=["./docs"],
        ai_client=ai,
        chunk_size=500,
        chunk_overlap=50,
        top_k=3,
    )
    
    # 索引文档
    print("正在索引文档...")
    await rag.index()
    print("索引完成!")
    
    # 查询
    question = "ThinkAi框架支持哪些AI模型?"
    print(f"\n问题: {question}")
    
    answer = await rag.query(question)
    print(f"\n回答: {answer}")


if __name__ == "__main__":
    asyncio.run(example_rag())
