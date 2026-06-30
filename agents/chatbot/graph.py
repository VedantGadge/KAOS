"""
Chatbot Agent — LangGraph ReAct Agent

Unlike the other KAOS agents (Triager, Review Manager, Ops Manager), the Chatbot
legitimately needs an LLM because it must interpret free-text user questions and
decide which tool to call. We use LangGraph's create_react_agent for a structured,
traceable ReAct loop instead of the manual BaseAgent loop.

Tools available:
  - get_bug_timeline: Full lifecycle of a service's bugs
  - search_events: Keyword search across all events
  - find_team_info: Who owns a service
  - get_jira_status: Current Jira ticket status
  - get_bug_solution_details: Technical details of how a bug was fixed
"""

from langgraph.prebuilt import create_react_agent

from shared.tools import (
    get_bug_timeline,
    search_events,
    find_team_info,
    get_jira_status,
    get_bug_solution_details,
)
from shared.logger import logger

import boto3
from config.settings import settings


SYSTEM_PROMPT = """You are the KAOS Chatbot (Agent 4).
Your job is to help employees understand what is happening in the system.
You have access to the entire event history, bug tracking, and team structure.

# Capabilities
1. **Bug History**: If asked "What happened with X?", use `get_bug_timeline`.
2. **Search**: If asked "Did we have any NPEs?", use `search_events`.
3. **Team Info**: If asked "Who owns X?", use `find_team_info`.
4. **Ticket Status**: If asked "Is the ticket resolved?", use `get_jira_status`.
5. **Solution Details**: If asked "How was X fixed?", use `get_bug_solution_details`.

# Rules
- Be concise and friendly.
- Synthesize the tool outputs into a clear narrative.
- If the tool returns "No events found", tell the user you couldn't find anything.
- If a bug was "Rejected" or "Failed", explain WHY based on the tool output details.
- Always mention WHO (Actor) performed an action if available.
"""

CHATBOT_TOOLS = [
    get_bug_timeline,
    search_events,
    find_team_info,
    get_jira_status,
    get_bug_solution_details,
]


def build_chatbot_graph():
    """
    Build and compile the Chatbot LangGraph ReAct agent.

    Uses AWS Bedrock (Amazon Nova Lite) as the LLM, with the chatbot tools
    bound for automatic tool calling.
    """
    from langchain_aws import ChatBedrock

    bedrock_client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

    llm = ChatBedrock(
        client=bedrock_client,
        model_id="amazon.nova-lite-v1:0",
        model_kwargs={"maxTokenCount": 4096, "temperature": 0.0},
    )

    logger.info("🧠 Building Chatbot ReAct LangGraph...")

    graph = create_react_agent(
        model=llm,
        tools=CHATBOT_TOOLS,
        prompt=SYSTEM_PROMPT,
    )

    logger.info("✅ Chatbot Graph Compiled")
    return graph
