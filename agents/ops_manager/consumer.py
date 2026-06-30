import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.consumer_base import BaseAgentConsumer
from agents.ops_manager.graph import build_ops_graph
from shared.logger import logger


class OpsManagerConsumer(BaseAgentConsumer):
    def __init__(self):
        prod_group = "ops-manager-prod-group"
        logger.info(f"🔧 Production Mode: Using stable group {prod_group} (v2 - LangGraph)")

        super().__init__(
            group_id=prod_group,
            topics=["ops.deploy.status"],
        )

        logger.info("🧠 Compiling Ops Manager LangGraph...")
        self.graph = build_ops_graph()
        logger.info("✅ Graph Compiled")

    def process_message(self, message: dict):
        """
        Handle 'ops.deploy.status' events (deployment outcomes from AWS CodePipeline).
        """
        logger.info(
            f"📦 OpsManager received: {message.get('status')} for {message.get('pipeline')} "
            f"(Execution: {message.get('execution_id')})"
        )
        try:
            self.graph.invoke({"message": message})
            logger.info("✅ Ops Graph Execution Complete")
        except Exception as e:
            logger.error(f"❌ Ops Graph Execution Failed: {e}")


if __name__ == "__main__":
    logger.info("🚀 Starting Agent 3 (Ops Manager) Listener...")
    consumer = OpsManagerConsumer()
    consumer.run()
