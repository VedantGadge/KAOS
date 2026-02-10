from langchain_aws import ChatBedrock
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
import boto3

class BaseAgent:
    def __init__(self, name: str, tools: list, instructions: str):
        self.name = name
        self.tools = tools
        self.instructions = instructions
        
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
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            model_kwargs={"max_tokens": 1024}
        )
        
        # Create Prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.instructions),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        # Create Agent
        self.agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)
        self.executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)

    def run(self, task: str):
        print(f"🤖 [{self.name}] Thinking via LangChain...")
        # LangChain expects 'input' key
        try:
            result = self.executor.invoke({"input": task})
            return result['output']
        except Exception as e:
            print(f"❌ LangChain Error: {e}")
            return str(e)
