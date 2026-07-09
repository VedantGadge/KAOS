import requests
import json
import time

# Deployed API Gateway URL
API_URL = "https://dnqhak6oxc.execute-api.ap-south-1.amazonaws.com"

print("🚀 Starting KAOS E2E Webhook Tests...")

# 1. Test Sentry Webhook (Triggers Triager)
print("\n[1/3] Testing Sentry Webhook (Triager Flow)...")
sentry_payload = {
    "id": f"evt-{int(time.time())}",
    "project_name": "checkout-service",
    "message": "Connection refused to payment gateway",
    "level": "error"
}
resp_sentry = requests.post(
    f"{API_URL}/webhooks/sentry",
    json=sentry_payload
)
print(f"Status: {resp_sentry.status_code}")
print(f"Response: {resp_sentry.text}")

# 2. Test GitHub Webhook (Triggers Review Manager)
print("\n[2/3] Testing GitHub PR Webhook (Review Manager Flow)...")
github_payload = {
    "action": "opened",
    "pull_request": {
        "number": 101,
        "user": {"login": "alice-dev"},
        "title": "feat: integrate new stripe API"
    },
    "repository": {
        "name": "payment-backend"
    }
}
headers = {"X-GitHub-Event": "pull_request"}
resp_github = requests.post(
    f"{API_URL}/webhooks/github",
    json=github_payload,
    headers=headers
)
print(f"Status: {resp_github.status_code}")
print(f"Response: {resp_github.text}")

# 3. Test Deployment Webhook (Triggers Ops Manager)
print("\n[3/3] Testing Deployment Webhook (Ops Manager Flow)...")
deploy_payload = {
    "service": "auth-service",
    "version": f"v1.2.{int(time.time())}",
    "status": "failure",
    "logs": "https://ci.example.com/logs/123",
    "author": "bob-dev"
}
resp_deploy = requests.post(
    f"{API_URL}/webhooks/deployment",
    json=deploy_payload
)
print(f"Status: {resp_deploy.status_code}")
print(f"Response: {resp_deploy.text}")

print("\n✅ All webhooks sent! The events have been published to Confluent Kafka and AWS Event Source Mappings are currently routing them to the Agents.")
print("Check AWS CloudWatch Logs (for kaos-triager, kaos-review-manager, and kaos-ops-manager) to see the agents in action!")
