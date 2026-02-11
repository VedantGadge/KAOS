from shared.kafka.client import KafkaClient
from shared.models.events import DevUpdateEvent, DevDecisionEvent
from datetime import datetime
import json
import argparse


def produce_pr_event(event_type: str, repo: str = "PaymentService", author: str = "Charlie",
                     actor: str = "Alice", comment: str = "", pr_id: int = 101):
    kafka = KafkaClient()
    producer = kafka.create_producer()

    def delivery_report(err, msg):
        if err is not None:
            print(f"❌ Message delivery failed: {err}")
        else:
            print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}]")

    if event_type == "push":
        # Simulate a PR push / synchronize event
        event = DevUpdateEvent(
            event="PR_SYNCHRONIZE",
            repo=repo,
            pr_id=pr_id,
            author=author,
            commit_sha="abc123def456",
            timestamp=datetime.now().isoformat()
        )
        topic = "dev.pr.updates"
        value = event.model_dump_json()
        print(f"🚀 Sending PR push event for {repo} (PR #{pr_id}, author: {author}) to {topic}...")
        producer.produce(topic, value.encode('utf-8'), callback=delivery_report)

    elif event_type == "conflict":
        # Simulate a merge conflict event
        event = DevUpdateEvent(
            event="MERGE_CONFLICT",
            repo=repo,
            pr_id=pr_id,
            author=author,
            commit_sha="abc123def456",
            timestamp=datetime.now().isoformat()
        )
        topic = "dev.pr.updates"
        value = event.model_dump_json()
        print(f"🚀 Sending merge conflict event for {repo} (PR #{pr_id}, author: {author}) to {topic}...")
        producer.produce(topic, value.encode('utf-8'), callback=delivery_report)

    elif event_type == "rejection":
        # Simulate a PR rejection
        event = DevDecisionEvent(
            event="REVIEW_SUBMITTED",
            pr_id=pr_id,
            repo=repo,
            actor=actor,
            decision="CHANGES_REQUESTED",
            comment=comment or "Please fix the bug on line 45.",
            timestamp=datetime.now().isoformat()
        )
        topic = "dev.pr.decisions"
        value = event.model_dump_json()
        print(f"🚀 Sending PR rejection for {repo} (PR #{pr_id}, reviewer: {actor}) to {topic}...")
        producer.produce(topic, value.encode('utf-8'), callback=delivery_report)

    elif event_type == "approval":
        # Simulate a PR approval
        event = DevDecisionEvent(
            event="REVIEW_SUBMITTED",
            pr_id=pr_id,
            repo=repo,
            actor=actor,
            decision="APPROVED",
            comment=comment or "Looks good!",
            timestamp=datetime.now().isoformat()
        )
        topic = "dev.pr.decisions"
        value = event.model_dump_json()
        print(f"🚀 Sending PR approval for {repo} (PR #{pr_id}, reviewer: {actor}) to {topic}...")
        producer.produce(topic, value.encode('utf-8'), callback=delivery_report)

    else:
        print(f"❌ Unknown event type: {event_type}. Use: push, conflict, rejection, approval")
        return

    producer.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Produce test PR events for Agent 2")
    parser.add_argument("--type", required=True, choices=["push", "conflict", "rejection", "approval"],
                        help="Event type: push, conflict, rejection, approval")
    parser.add_argument("--repo", default="PaymentService", help="Repository name")
    parser.add_argument("--author", default="Charlie", help="PR author name")
    parser.add_argument("--actor", default="Alice", help="Reviewer name (for rejection/approval)")
    parser.add_argument("--comment", default="", help="Review comment (for rejection)")
    parser.add_argument("--pr-id", type=int, default=101, help="PR number")
    args = parser.parse_args()

    produce_pr_event(
        event_type=args.type,
        repo=args.repo,
        author=args.author,
        actor=args.actor,
        comment=args.comment,
        pr_id=args.pr_id
    )
