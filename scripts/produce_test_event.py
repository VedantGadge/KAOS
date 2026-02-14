import sys
import os
import json
import time

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.kafka.client import KafkaClient

import argparse

def produce_test_events():
    parser = argparse.ArgumentParser(description="Produce KAOS Test Events")
    parser.add_argument("--bug", action="store_true", help="Send a Sentry Bug Report (Triager)")
    parser.add_argument("--pr", action="store_true", help="Send a PR Opened Event (Review Manager)")
    parser.add_argument("--reject", action="store_true", help="Send a PR Rejection Decision")
    parser.add_argument("--approve", action="store_true", help="Send a PR Approval Decision")
    parser.add_argument("--all", action="store_true", help="Send ALL events in sequence")
    
    args = parser.parse_args()
    
    # Default to help if no args
    if not any([args.bug, args.pr, args.reject, args.approve, args.all]):
        parser.print_help()
        return

    client = KafkaClient()
    producer = client.create_producer()
    
    print("🚀 Connecting to Confluent Cloud...")

    # Shared Bug Title for linking
    # IMPORTANT: Triager prefixes summary with [Service], so we must match that for lookups to work
    raw_bug_title = "NullPointerException in ProcessTransaction"
    service_name = "PaymentService"
    
    # The summary stored in Jira/Notion will be: "[PaymentService] NullPointerException..."
    linked_summary_search_term = f"[{service_name}] {raw_bug_title}"

    # 1. Simulate Sentry Bug (for Triager)
    if args.bug or args.all:
        bug_event = {
            "event_id": "bug-001",
            "service_name": service_name,
            "severity": "HIGH",
            "error_message": raw_bug_title,
            "timestamp": str(time.time())
        }
        
        producer.produce(topic="system.quality.reports", key="bug-001", value=json.dumps(bug_event))
        print(f"📨 [1/4] Bug Reported: {raw_bug_title}")
        if args.all: time.sleep(2)

    # 2. Simulate PR Opened (for Review Manager)
    if args.pr or args.all:
        pr_event = {
            "event": "PR_OPENED",
            "repo": service_name,
            "pr_id": 105,
            "author": "Dave", # Dave fixes the bug assigned to him
            "title": linked_summary_search_term, # Linking via FULL summary helps finding it
            "timestamp": str(time.time())
        }

        producer.produce(topic="dev.pr.updates", key="pr-105", value=json.dumps(pr_event))
        print(f"📨 [2/4] PR #105 Opened (Fixes Bug)")
        if args.all: time.sleep(2)

    # 3. Simulate PR Rejection (Review Manager)
    if args.reject or args.all:
        reject_event = {
            "event": "REVIEW_SUBMITTED",
            "repo": service_name,
            "pr_id": 105,
            "actor": "Charlie", # Reviewer
            "pr_author": "Dave", # Developer (Added for notification)
            "decision": "CHANGES_REQUESTED",
            "comment": "Please add unit tests for the null check.",
            "related_bug_title": linked_summary_search_term, # Explicit link
            "timestamp": str(time.time())
        }
        
        producer.produce(topic="dev.pr.decisions", key="review-105-1", value=json.dumps(reject_event))
        print(f"📨 [3/4] PR #105 Rejected")
        if args.all: time.sleep(2)

    # 4. Simulate PR Approval (Review Manager)
    if args.approve or args.all:
        approve_event = {
            "event": "REVIEW_SUBMITTED",
            "repo": service_name,
            "pr_id": 105,
            "actor": "Charlie", # Reviewer
            "pr_author": "Dave", # Developer (Added for notification)
            "decision": "APPROVED",
            "comment": "LGTM! Ready to merge.",
            "related_bug_title": linked_summary_search_term,
            "timestamp": str(time.time())
        }
        
        producer.produce(topic="dev.pr.decisions", key="review-105-2", value=json.dumps(approve_event))
        print(f"📨 [4/4] PR #105 Approved")

    # Flush to ensure delivery
    producer.flush()
    print("✅ Selected events sent!")

if __name__ == "__main__":
    produce_test_events()
