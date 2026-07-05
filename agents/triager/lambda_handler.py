import base64
import json
import os
import sys

# Ensure project root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.triager.graph import build_triager_graph
from shared.logger import logger

# Compile the graph on warm start
logger.info("🧠 Compiling Triager LangGraph for Lambda...")
triager_graph = build_triager_graph()
logger.info("✅ Triager LangGraph Compiled")

def handler(event, context):
    """
    AWS Lambda Handler for Triager Agent.
    Triggered by AWS MSK Topic Event Source Mapping.
    """
    logger.info(f"📥 Received Lambda MSK trigger event: {json.dumps(event)}")
    
    records = event.get("records", {})
    processed_count = 0
    
    for topic_partition, record_list in records.items():
        for record in record_list:
            base64_val = record.get("value", "")
            if not base64_val:
                logger.warning(f"⚠️ Empty record value in {topic_partition}")
                continue
                
            try:
                decoded_val = base64.b64decode(base64_val).decode("utf-8")
                message = json.loads(decoded_val)
                logger.info(f"📥 Processing message from {topic_partition} (offset: {record.get('offset')}): {message}")
                
                # Execute compiled LangGraph StateGraph
                triager_graph.invoke({"message": message})
                processed_count += 1
                logger.info("✅ Graph Execution Complete")
            except Exception as e:
                logger.error(f"❌ Graph Execution Failed: {e}", exc_info=True)
                # Keep processing other records in the batch, but log failure.
                
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Events processed successfully",
            "count": processed_count
        })
    }
