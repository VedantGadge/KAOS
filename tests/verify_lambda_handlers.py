import base64
import json
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.triager.lambda_handler import handler as triager_handler
from agents.review_manager.lambda_handler import handler as review_handler
from agents.ops_manager.lambda_handler import handler as ops_handler

def test_triager_handler():
    print("\n--- 🧪 Testing Triager Lambda Handler ---")
    bug_event = {
        "event_id": "mock-bug-999",
        "service_name": "auth-service",
        "severity": "CRITICAL",
        "error_message": "Connection timeout when contacting database. Pool exhausted.",
        "suggested_assignee": "VedantGadge",
        "timestamp": "2026-07-05T20:00:00Z"
    }
    
    encoded = base64.b64encode(json.dumps(bug_event).encode("utf-8")).decode("utf-8")
    
    event = {
        "eventSource": "aws:kafka",
        "records": {
            "system.quality.reports-0": [
                {
                    "topic": "system.quality.reports",
                    "partition": 0,
                    "offset": 12,
                    "value": encoded
                }
            ]
        }
    }
    
    response = triager_handler(event, None)
    print(f"Response: {response}")

def test_review_manager_handler():
    print("\n--- 🧪 Testing Review Manager Lambda Handler ---")
    pr_event = {
        "event": "PR_OPENED",
        "repo": "payment-service",
        "pr_id": 108,
        "author": "VedantGadge",
        "title": "Fix memory leak in payment processor",
        "timestamp": "2026-07-05T20:01:00Z"
    }
    
    encoded = base64.b64encode(json.dumps(pr_event).encode("utf-8")).decode("utf-8")
    
    event = {
        "eventSource": "aws:kafka",
        "records": {
            "dev.pr.updates-0": [
                {
                    "topic": "dev.pr.updates",
                    "partition": 0,
                    "offset": 23,
                    "value": encoded
                }
            ]
        }
    }
    
    response = review_handler(event, None)
    print(f"Response: {response}")

def test_ops_manager_handler():
    print("\n--- 🧪 Testing Ops Manager Lambda Handler ---")
    deploy_event = {
        "execution_id": "exe-us-east-1-999",
        "pipeline": "auth-service-pipeline",
        "status": "SUCCEEDED",
        "author": "VedantGadge",
        "timestamp": "2026-07-05T20:02:00Z"
    }
    
    encoded = base64.b64encode(json.dumps(deploy_event).encode("utf-8")).decode("utf-8")
    
    event = {
        "eventSource": "aws:kafka",
        "records": {
            "ops.deploy.status-0": [
                {
                    "topic": "ops.deploy.status",
                    "partition": 0,
                    "offset": 88,
                    "value": encoded
                }
            ]
        }
    }
    
    response = ops_handler(event, None)
    print(f"Response: {response}")

if __name__ == "__main__":
    # Configure env to bypass local sentence-transformers (use Bedrock mock route inside logic)
    os.environ["USE_BEDROCK_EMBEDDINGS"] = "true"
    
    # Run tests
    test_triager_handler()
    test_review_manager_handler()
    test_ops_manager_handler()
    print("\n🎉 Local Lambda validation completed successfully!")
