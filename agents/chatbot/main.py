from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base import BaseAgent
from agents.chatbot.tools import tools as chatbot_tools
from shared.logger import setup_logger

logger = setup_logger("chatbot-agent")

app = FastAPI(title="KAOS Chatbot Agent")

# Allow CORS for Control Plane UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to control plane URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# System Prompt for the Chatbot
SYSTEM_PROMPT = """
You are the KAOS Chatbot (Agent 4).
Your job is to help employees understand what is happening in the system.
You have access to the entire event history, bug tracking, and team structure.

# Capabilities
1. **Bug History**: If asked "What happened with X?", use `get_bug_timeline`.
2. **Search**: If asked "Did we have any NPEs?", use `search_events`.
3. **Team Info**: If asked "Who owns X?", use `find_team_info`.
4. **Ticket Status**: If asked "Is the ticket resolved?", use `get_jira_status`.

# Rules
- Be concise and friendly.
- Synthesize the tool outputs into a clear narrative.
- If the tool returns "No events found", tell the user you couldn't find anything.
- If a bug was "Rejected" or "Failed", explain WHY based on the tool output details.
- Always mention WHO (Actor) performed an action if available.
"""

class ChatRequest(BaseModel):
    question: str
    user_id: str = "anonymous"

class ChatResponse(BaseModel):
    answer: str
    tool_calls: list = [] # Optional debugging info

@app.get("/")
def health_check():
    return {"status": "running", "service": "kaos-chatbot"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the KAOS system.
    """
    logger.info(f"🗣️ User ({request.user_id}): {request.question}")
    
    try:
        # Initialize the AI Agent with our tools
        agent = BaseAgent(
            name="Chatbot",
            tools=chatbot_tools,
            instructions=SYSTEM_PROMPT
        )
        
        # Run the agent loop
        response = agent.run(request.question)
        
        logger.info(f"🤖 Bot: {response}")
        
        return ChatResponse(
            answer=response
        )

    except Exception as e:
        logger.error(f"❌ Chatbot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run on port 8001 to avoid conflict with Ingestion (8000) and Control Plane (8080)
    uvicorn.run(app, host="0.0.0.0", port=8001)
