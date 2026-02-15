from shared.kafka.client import KafkaClient
from shared.models.events import DevUpdateEvent, DevDecisionEvent
from agents.base import BaseAgent
from agents.review_manager.tools import tools as review_tools
import json

# Kafka Topics
PR_UPDATES_TOPIC = "dev.pr.updates"
PR_DECISIONS_TOPIC = "dev.pr.decisions"
GROUP_ID = "agent-2-review-manager-group"

# System Prompt
SYSTEM_PROMPT = """
You are the Review Manager Agent (Agent 2).
Your goal is to manage the Pull Request lifecycle.

IMPORTANT RULES:
- You may call `send_slack_dm` MULTIPLE times if each call is for a DIFFERENT recipient (e.g., one DM to the reviewer, one DM to the author, one to #all-kaos). But do NOT send to the same channel twice.
- For all other tools (`check_pr_status`, `find_reviewer`), call each EXACTLY ONCE.
- When `find_reviewer` returns "Reviewer: Dave (Senior, Active) | Slack: #dave", use `#dave` as the channel for `send_slack_dm`. Do NOT guess channel names.
- The PR author's Slack channel is always `#<lowercase_author_name>` (e.g., "Charlie" → "#charlie").
- For `update_notion_status` and `update_jira_status`: You do NOT know the original bug title. Use the REPO NAME (e.g., "PaymentService") as the search term for both `title` and `summary`. The search will find the matching entry.

Handle the following scenarios:

## Scenario 1: PR_SYNCHRONIZE (New push / PR opened)
1. Call `check_pr_status` ONCE with the repo and pr_id.
2. If the PR is CLEAN:
   - Call `find_reviewer` ONCE (pass `service_name` = repo name, `pr_author` = author name, `pr_id` = Pull Request number).
   - Call `send_slack_dm` to DM the **reviewer** (use Slack channel from `find_reviewer`). Tell them to review PR #X in repo by author.
   - Call `send_slack_dm` to DM the **PR author** (channel = #<author_name>). Tell them that <reviewer_name> has been assigned to review their PR.
   - Call `send_slack_dm` to post in **#all-kaos**: "<author> has raised PR #X in <repo>. <reviewer> is assigned to review it."
   - Call `update_notion_status` with title = repo name and new_status = "To be reviwed".
   - Call `update_jira_status` with summary = repo name and comment = "PR #X raised by <author>. Reviewer <reviewer> assigned."
3. If MERGE_CONFLICT:
   - Call `send_slack_dm` to DM the **PR author** to resolve the conflict.
   - Call `update_notion_status` with title = repo name and new_status = "Needs attention".
   - Call `update_jira_status` with summary = repo name and comment = "Merge conflict detected in PR #X. Developer has been notified to resolve it."

## Scenario 2: MERGE_CONFLICT (Explicit conflict event)
- Call `send_slack_dm` to DM the **PR author** to resolve the merge conflict.
- Call `update_notion_status` with title = repo name and new_status = "Needs attention".
- Call `update_jira_status` with summary = repo name and comment = "Merge conflict detected in PR #X. Developer has been notified to resolve it."

## Scenario 3: REVIEW_SUBMITTED + CHANGES_REQUESTED (PR Rejected)
- Call `send_slack_dm` to DM the **PR author** with the reviewer's comment/feedback.
- Call `send_slack_dm` to post in **#all-kaos**: "🔄 PR #X in <repo> needs changes. Reviewer: <actor>."
- Call `update_notion_status` with title = repo name and new_status = "Needs attention".
- Call `update_jira_status` with summary = repo name and comment = "PR #X changes requested by <actor>: <comment>".

## Scenario 4: REVIEW_SUBMITTED + APPROVED (PR Approved)
- Call `send_slack_dm` to post in **#all-kaos**: "✅ PR #X in <repo> has been approved by <actor>. Ready for merge!"
- Call `update_notion_status` with title = repo name and new_status = "To be deployed".
- Call `update_jira_status` with summary = repo name and comment = "PR #X approved by <actor>. Ready for merge."
- Then respond with a brief summary.

After handling the scenario, respond with a brief summary.
"""


def process_pr_update(msg_value: str):
    """Process a PR update event (pushes, opens)."""
    try:
        event_data = json.loads(msg_value)
        event = DevUpdateEvent(**event_data)
        print(f"✅ [Agent 2] PR Update: {event.event} | Repo: {event.repo} | PR #{event.pr_id} | Author: {event.author}")

        agent = BaseAgent(
            name="ReviewManager",
            tools=review_tools,
            instructions=SYSTEM_PROMPT
        )

        task = f"""
        PR Update Event Received:
        Event Type: {event.event}
        Repository: {event.repo}
        PR Number: {event.pr_id}
        Author: {event.author}
        Commit SHA: {event.commit_sha}

        Please handle this based on the event type.
        """

        agent.run(task)

    except Exception as e:
        print(f"❌ [Agent 2] Failed to process PR update: {e}")


def process_pr_decision(msg_value: str):
    """Process a PR decision event (approvals, rejections)."""
    try:
        event_data = json.loads(msg_value)
        event = DevDecisionEvent(**event_data)
        print(f"✅ [Agent 2] PR Decision: {event.decision} | Repo: {event.repo} | PR #{event.pr_id} | Actor: {event.actor}")

        agent = BaseAgent(
            name="ReviewManager",
            tools=review_tools,
            instructions=SYSTEM_PROMPT
        )

        task = f"""
        PR Decision Event Received:
        Event Type: {event.event}
        Repository: {event.repo}
        PR Number: {event.pr_id}
        Actor (Reviewer): {event.actor}
        Decision: {event.decision}
        Comment: {event.comment or 'No comment provided.'}

        Please handle this based on the decision.
        """

        agent.run(task)

    except Exception as e:
        print(f"❌ [Agent 2] Failed to process PR decision: {e}")


def main():
    print("Agent 2: Review Manager Starting...")
    print(f"🔌 Connecting to Kafka Topics: {PR_UPDATES_TOPIC}, {PR_DECISIONS_TOPIC}...")

    kafka = KafkaClient()
    consumer = kafka.create_consumer(group_id=GROUP_ID)
    consumer.subscribe([PR_UPDATES_TOPIC, PR_DECISIONS_TOPIC])

    print("🎧 Listening for PR events...")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            topic = msg.topic()
            value = msg.value().decode('utf-8')

            if topic == PR_UPDATES_TOPIC:
                process_pr_update(value)
            elif topic == PR_DECISIONS_TOPIC:
                process_pr_decision(value)

    except KeyboardInterrupt:
        print("🛑 Agent 2 stopping...")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
