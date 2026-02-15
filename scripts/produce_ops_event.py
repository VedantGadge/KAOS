import sys
import os
import json
import time
import argparse

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.kafka.client import KafkaClient

def produce_ops_events():
    parser = argparse.ArgumentParser(description="Produce KAOS Ops Test Events")
    parser.add_argument("--success", action="store_true", help="Send a Pipeline Success Event")
    parser.add_argument("--failure", action="store_true", help="Send a Pipeline Failure Event")
    parser.add_argument("--merge", action="store_true", help="Send a Merge/Trigger Event")
    
    args = parser.parse_args()
    
    if not any([args.success, args.failure, args.merge]):
        parser.print_help()
        return

    client = KafkaClient()
    producer = client.create_producer()
    
    pipeline_name = "payment-service-prod"
    repo_name = "PaymentService"

    # 1. Simulate Merge Detected (Trigger Pipeline)
    if args.merge:
        # In a real flow, this might be triggered by Agent 2 or a GitHub Action
        # For testing Agent 3's trigger logic:
        merge_event = {
            "execution_id": "exe-000",
            "pipeline": repo_name,
            "status": "MERGE_DETECTED",
            "timestamp": str(time.time())
        }
        producer.produce(topic="ops.deploy.status", key="merge-000", value=json.dumps(merge_event))
        print(f"📨 Merge Detected for {repo_name}. Triggering pipeline...")

    # 2. Simulate Pipeline Success
    if args.success:
        success_event = {
            "execution_id": "exe-123",
            "pipeline": repo_name,
            "status": "SUCCEEDED",
            "timestamp": str(time.time())
        }
        producer.produce(topic="ops.deploy.status", key="success-123", value=json.dumps(success_event))
        print(f"📨 Deployment SUCCEEDED for {repo_name}")

    # 3. Simulate Pipeline Failure
    if args.failure:
        failure_event = {
            "execution_id": "exe-456",
            "pipeline": pipeline_name,
            "status": "FAILED",
            "failure_stage": "Build",
            "author": "Dave", # Original PR author
            "logs_url": "s3://build-logs/payment-service/exe-456",
            "timestamp": str(time.time())
        }
        producer.produce(topic="ops.deploy.status", key="failure-456", value=json.dumps(failure_event))
        print(f"📨 Deployment FAILED for {pipeline_name}")

    producer.flush()
    print("✅ Ops events sent!")

if __name__ == "__main__":
    produce_ops_events()
