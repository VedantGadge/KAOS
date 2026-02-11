from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from config.settings import settings
import boto3
import json

class BaseAgent:
    def __init__(self, name: str, tools: list, instructions: str):
        self.name = name
        self.tools = tools
        self.instructions = instructions
        
        # Create tool mapping for execution
        self.tool_map = {t.name: t for t in tools}
        
        # Initialize Bedrock Client
        self.client = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # Initialize LLM
        self.llm = ChatBedrock(
            client=self.client,
            model_id="amazon.nova-lite-v1:0",
            model_kwargs={"maxTokenCount": 4096, "temperature": 0.7}
        )
        
        # Bind tools to LLM
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = self.llm

    def run(self, task: str):
        print(f"🤖 [{self.name}] Thinking via Custom Loop...")
        
        messages = [
            SystemMessage(content=self.instructions),
            HumanMessage(content=task)
        ]
        
        # Simple ReAct Loop (Max 5 iterations)
        for _ in range(5):
            try:
                response = self.llm_with_tools.invoke(messages)
            except Exception as e:
                print(f"❌ LLM Invoke Error: {e}")
                return f"Error interacting with LLM: {str(e)}"
            
            messages.append(response)
            
            # Check for tool calls
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]
                    
                    print(f"🛠️ Tool Call: {tool_name}({tool_args})")
                    
                    if tool_name in self.tool_map:
                        try:
                            # Execute tool
                            tool_result = self.tool_map[tool_name].invoke(tool_args)
                            print(f"✅ Tool Result: {tool_result}")
                        except Exception as e:
                            tool_result = f"Error executing tool {tool_name}: {str(e)}"
                            print(f"❌ Tool Execution Error: {tool_result}")
                    else:
                        tool_result = f"Error: Tool {tool_name} not found."
                    
                    # Add tool result to history
                    messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
            else:
                # No more tools, just return the content
                return response.content
                
        return "Agent stopped after max iterations."
