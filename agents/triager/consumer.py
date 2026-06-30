import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.consumer_base import BaseAgentConsumer
from agents.triager.graph import build_triager_graph
from shared.logger import logger
from config.settings import settings


class TriagerConsumer(BaseAgentConsumer):
    def __init__(self):
        # Production Group ID ensures we don't re-process events we've already committed.
        # If you restart the agent, it picks up where it left off.
        prod_group = settings.GROUP_TRIAGER_PROD
        logger.info(f"🔧 Production Mode: Using stable group {prod_group}")
        
        super().__init__(
            group_id=prod_group,
            topics=[settings.TOPIC_QUALITY_REPORTS]
        )
        
        # Compile the graph once on startup
        logger.info("🧠 Compiling Triager LangGraph...")
        self.graph = build_triager_graph()
        logger.info("✅ Graph Compiled")

    def process_message(self, message: dict):
        """
        Handle 'system.quality.reports' events (Bugs/Incidents)
        by routing them through the LangGraph state machine.
        """
        # Execute the compiled graph with the initial state
        try:
            self.graph.invoke({"message": message})
            logger.info("✅ Graph Execution Complete")
        except Exception as e:
            logger.error(f"❌ Graph Execution Failed: {e}")


if __name__ == "__main__":
    logger.info("🚀 Starting Agent 1 (Triager) Listener...")
    consumer = TriagerConsumer()
    consumer.run()
