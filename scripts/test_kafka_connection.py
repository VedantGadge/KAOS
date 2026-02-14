import sys
import os

# Add the parent directory to sys.path to allow imports from shared
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.kafka.client import KafkaClient
from confluent_kafka.admin import AdminClient

def test_connection():
    print("🔌 Connecting to Confluent Cloud...")
    
    try:
        # Initialize Client
        client = KafkaClient()
        
        # Use AdminClient to list topics (fastest way to check creds)
        admin_client = AdminClient(client.conf)
        
        # Timeout of 10s
        cluster_metadata = admin_client.list_topics(timeout=10)
        
        if cluster_metadata.topics:
            print("✅ Connection Successful!")
            print(f"📊 Found {len(cluster_metadata.topics)} topics:")
            for topic in cluster_metadata.topics:
                print(f"   - {topic}")
        else:
            print("⚠️ Connection successful but no topics found.")
            
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        print("\nPossible fixes:")
        print("1. Check SASL_USERNAME and SASL_PASSWORD in .env")
        print("2. Ensure BOOTSTRAP_SERVERS is correct")
        print("3. Check internet connection / firewall")

if __name__ == "__main__":
    test_connection()
