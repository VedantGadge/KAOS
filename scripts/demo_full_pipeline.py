import time
import requests
import json
import sys

# Configuration
INGESTION_URL = "http://localhost:8000"
SERVICE_NAME = "PaymentService"
PR_ID = 102
AUTHOR = "Dave"
REVIEWER = "Sarah"

def print_header(title):
    print("\n" + "="*60)
    print(f" 🎬  {title}")
    print("="*60)

def step(msg):
    print(f"\n👉 {msg}")
    time.sleep(1.5)

def send_deployment_failure():
    print_header("SCENARIO: Deployment Failure")
    step(f"Simulating deployment failure for {SERVICE_NAME}...")
    
    payload = {
        "service": SERVICE_NAME,
        "version": "v1.2.0",
        "status": "failure",
        "logs": "CRITICAL: NullPointerException in validation logic.\n   at PaymentProcessor.validate(Processor.java:45)\n   at Main.run(Main.java:12)",
        "author": AUTHOR,
        "reviewer": REVIEWER
    }
    
    try:
        resp = requests.post(f"{INGESTION_URL}/webhooks/deployment", json=payload)
        print(f"   📨 Webhook Sent: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

def send_pr_open():
    print_header("SCENARIO: Developer Fixes the Bug")
    step(f"Developer {AUTHOR} opens PR #{PR_ID} to fix the NPE...")
    
    # GitHub 'pull_request' opened payload structure (simplified)
    payload = {
        "action": "opened",
        "pull_request": {
            "number": PR_ID,
            "title": f"Fix NullPointerException in {SERVICE_NAME} validation logic",
            "body": "This PR adds a null check to the input payload before processing. It also adds a unit test.",
            "user": {"login": AUTHOR},
            "state": "open"
        },
        "repository": {"name": SERVICE_NAME}
    }
    
    headers = {"X-GitHub-Event": "pull_request"}
    
    try:
        resp = requests.post(f"{INGESTION_URL}/webhooks/github", json=payload, headers=headers)
        print(f"   📨 Webhook Sent: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

def send_pr_merge():
    print_header("SCENARIO: PR Merged & Closed")
    step(f"Maintainer merged PR #{PR_ID}...")
    
    # GitHub 'pull_request' closed (merged) payload
    payload = {
        "action": "closed",
        "pull_request": {
            "number": PR_ID,
            "title": f"Fix NullPointerException in {SERVICE_NAME} validation logic",
            "user": {"login": AUTHOR},
            "merged": True,
            "state": "closed"
        },
        "repository": {"name": SERVICE_NAME}
    }
    
    headers = {"X-GitHub-Event": "pull_request"}
    
    try:
        resp = requests.post(f"{INGESTION_URL}/webhooks/github", json=payload, headers=headers)
        print(f"   📨 Webhook Sent: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

def main():
    print("\n⚠️  Ensure the Ingestion Agent is running on localhost:8000")
    print("   Ensure the Review Manager and Triager are running to see the full effect.\n")
    
    input("Press Enter to start the demo simulation...")
    
    # 1. Deployment Failure
    send_deployment_failure()
    
    step("Wait for Triager to open Jira ticket and Notion page...")
    time.sleep(3)
    
    # 2. PR Open (The Fix)
    input("\n[Action] Developer is fixing the bug. Press Enter to simulate PR Creation...")
    send_pr_open()
    
    step("Wait for Review Manager to assign reviewer...")
    time.sleep(3)
    
    # 3. PR Merge (The Resolution)
    input("\n[Action] PR approved and merging. Press Enter to simulate PR Merge...")
    send_pr_merge()
    
    print_header("DEMO COMPLETE")
    print(f"Now you can ask the Chatbot: 'How was the bug in {SERVICE_NAME} solved?'")
    print("It should retrieve the details of PR #102.")

if __name__ == "__main__":
    main()
