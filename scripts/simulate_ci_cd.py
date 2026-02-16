import time
import requests
import json
import sys

INGESTION_URL = "http://localhost:8000/webhooks/deployment"

def run_pipeline():
    print("🚀 Starting CI/CD Pipeline Simulation...")
    print("-" * 40)
    
    # Stage 1: Build
    print("📦 [Stage 1] Building Docker Image...")
    time.sleep(1)
    print("   ✅ Build Success: my-app:v1.0.5")
    
    # Stage 2: Test
    print("🧪 [Stage 2] Running Unit Tests...")
    time.sleep(1)
    print("   ✅ Tests Passed (45/45)")

    # Stage 3: Deploy
    print("🚢 [Stage 3] Deploying to Production...")
    time.sleep(2)
    
    # Simulate a Failure scenario
    # In a real pipeline, we would capture the command output
    deployment_status = "failure"
    logs = """
    Deploying to k8s-cluster-prod...
    Applying manifest services/payment-service.yaml...
    Error: ImagePullBackOff
    Reason: 403 Forbidden - Access Denied to ECR repository 'payment-service'.
    Check your IAM permissions for the node group.
    Rollback initiated...
    """
    
    print(f"   ❌ Deployment Failed!")
    print(f"   📄 Capturing logs...")

    # Stage 4: Notify Ingestion Service
    print("📢 [Stage 4] Sending Webhook to Ingestion Agent...")
    
    payload = {
        "service": "PaymentService",
        "version": "v1.0.5",
        "status": deployment_status,
        "logs": logs,
        "author": "Dave" # The person who triggered the build
    }
    
    try:
        resp = requests.post(INGESTION_URL, json=payload)
        if resp.status_code == 200:
            print(f"   ✅ Webhook Delivered: {resp.json()}")
        else:
            print(f"   ❌ Webhook Failed: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")

if __name__ == "__main__":
    run_pipeline()
