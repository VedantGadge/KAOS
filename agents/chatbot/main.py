from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.chatbot.graph import build_chatbot_graph
from shared.logger import logger

app = FastAPI(title="KAOS Chatbot Agent")

# Allow CORS for Control Plane UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to control plane URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    user_id: str = "anonymous"


class ChatResponse(BaseModel):
    answer: str


# Compile the graph once at module level
chatbot_graph = None


@app.on_event("startup")
def startup():
    global chatbot_graph
    logger.info("🚀 Compiling Chatbot LangGraph on startup...")
    chatbot_graph = build_chatbot_graph()
    logger.info("✅ Chatbot ready")


@app.get("/")
def health_check():
    return {"status": "running", "service": "kaos-chatbot"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the KAOS system via the LangGraph ReAct agent.
    """
    logger.info(f"🗣️ User ({request.user_id}): {request.question}")

    global chatbot_graph
    if chatbot_graph is None:
        logger.info("🧠 Lazy-loading Chatbot LangGraph...")
        chatbot_graph = build_chatbot_graph()

    try:
        result = chatbot_graph.invoke(
            {"messages": [{"role": "user", "content": request.question}]}
        )

        # Extract the final AI message from the graph output
        messages = result.get("messages", [])
        answer = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.type == "ai" and not msg.tool_calls:
                answer = msg.content
                break

        if not answer:
            answer = "I couldn't find an answer. Please try rephrasing your question."

        logger.info(f"🤖 Bot: {answer[:100]}...")

        return ChatResponse(answer=answer)

    except Exception as e:
        logger.error(f"❌ Chatbot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    # Run on port 8001 to avoid conflict with Ingestion (8000) and Control Plane (8080)
    uvicorn.run(app, host="0.0.0.0", port=8001)
