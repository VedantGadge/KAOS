import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.consumer_base import BaseAgentConsumer
from agents.review_manager.graph import build_review_graph
from shared.logger import logger
import json

class ReviewManagerConsumer(BaseAgentConsumer):
    def __init__(self):
        prod_group = "review-manager-prod-group"
        logger.info(f"🔧 Production Mode: Using stable group {prod_group} (v2 - LangGraph)")
        
        super().__init__(
            group_id=prod_group,
            topics=["dev.pr.updates", "dev.pr.decisions"]
        )
        
        logger.info("🧠 Compiling Review Manager LangGraph...")
        self.graph = build_review_graph()
        logger.info("✅ Graph Compiled")

    def process_message(self, message: dict):
        """
        Handle 'dev.pr.updates' and 'dev.pr.decisions' events.
        """
        logger.info(f"👀 ReviewManager received: {message.get('event')} for PR #{message.get('pr_id')} ({message.get('repo')})")
        try:
            self.graph.invoke({"message": message})
            logger.info("✅ Review Graph Execution Complete")
        except Exception as e:
            logger.error(f"❌ Review Graph Execution Failed: {e}")

if __name__ == "__main__":
    logger.info("🚀 Starting Agent 2 (Review Manager) Listener...")
    consumer = ReviewManagerConsumer()
    consumer.run()
