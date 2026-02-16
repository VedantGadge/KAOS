import requests
import json
import time

def test_sentry_webhook():
    url = "http://localhost:8000/webhooks/sentry"
    payload = {
        "id": "bug-test-001",
        "project_name": "PaymentService",
        "message": "NullPointerException in process_payment",
        "level": "error",
        "culprit": "payment_gateway",
        "url": "http://sentry.io/issues/123"
    }
    
    try:
        print(f"Sending POST to {url}...")
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Failed: {e}")

def test_deployment_webhook():
    url = "http://localhost:8000/webhooks/deployment"
    payload = {
        "service": "PaymentService",
        "version": "v1.2.3",
        "status": "failure",
        "logs": "CRITICAL: Database connection timeout\nStacktrace: ..."
    }
    
    try:
        print(f"Sending POST to {url}...")
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    # Wait for server to be ready
    time.sleep(2)
    test_sentry_webhook()
    print("-" * 20)
    test_deployment_webhook()
