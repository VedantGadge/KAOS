import sys
import time
import requests
import random
import argparse

# Configuration
INGESTION_URL = "http://localhost:8000/webhooks/github"

def simulate_git_output(repo_name="PaymentService", branch="fix/npe-payment-service"):
    print(f"Enumerating objects: 15, done.")
    time.sleep(0.1)
    print(f"Counting objects: 100% (15/15), done.")
    time.sleep(0.1)
    print(f"Delta compression using up to 12 threads")
    print(f"Compressing objects: 100% (8/8), done.")
    time.sleep(0.3)
    print(f"Writing objects: 100% (9/9), 1.45 KiB | 1.45 MiB/s, done.")
    print(f"Total 9 (delta 4), reused 0 (delta 0), pack-reused 0")
    time.sleep(0.2)
    print(f"remote: Resolving deltas: 100% (4/4), completed with 4 local objects.")
    time.sleep(0.4)
    print(f"To https://github.com/kaos-org/{repo_name}.git")
    print(f"   abc1234..def5678  {branch} -> {branch}")

def trigger_webhook(repo_name, branch, pr_number=105):
    """
    Send a payload to the Ingestion Agent to simulate a PR Open event.
    """
    payload = {
        "action": "opened",
        "pull_request": {
            "number": pr_number,
            "title": f"Fix NullPointerException in {repo_name}",
            "user": {"login": "dev_user"},
            "head": {"ref": branch},
            "html_url": f"https://github.com/kaos-org/{repo_name}/pull/{pr_number}"
        },
        "repository": {"name": repo_name}
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request"
    }

    try:
        response = requests.post(INGESTION_URL, json=payload, headers=headers)
        if response.status_code == 200:
            print("\n✅ System: Webhook triggered successfully (Ingestion Agent accepted it).")
        else:
            print(f"\n❌ System: Webhook failed with status {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"\n❌ System: Could not connect to Ingestion Agent at {INGESTION_URL}. Is it running?")

def main():
    parser = argparse.ArgumentParser(description="Simulate a Git Push event.")
    parser.add_argument("command", nargs="?", default="push", help="Git command (e.g., push)")
    parser.add_argument("--repo", default="PaymentService", help="Repository name")
    parser.add_argument("--branch", default="fix/npe-payment-service", help="Branch name")
    
    args = parser.parse_args()
    
    if args.command != "push":
        print(f"git: '{args.command}' is not a git command. See 'git --help'.")
        sys.exit(1)
        
    simulate_git_output(args.repo, args.branch)
    trigger_webhook(args.repo, args.branch)

if __name__ == "__main__":
    main()
