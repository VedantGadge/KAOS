import sys
import os
import time

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.kafka.client import KafkaClient
from confluent_kafka.admin import AdminClient, NewTopic

def reset_kafka_topics():
    print("🔥 CLEARING KAFKA TOPICS... THIS IS DESTRUCTIVE!")
    
    # 1. Connect
    client = KafkaClient()
    admin_client = AdminClient(client.conf)
    
    topics_to_reset = [
        "system.quality.reports",
        "dev.pr.updates",
        "dev.pr.decisions",
        "ops.deploy.status"
    ]
    
    # 2. Delete
    print(f"🗑️  Deleting topics: {topics_to_reset}...")
    fs = admin_client.delete_topics(topics_to_reset, operation_timeout=30)
    
    # Wait for futures
    for topic, f in fs.items():
        try:
            f.result()  # The result itself is None
            print(f"   ✅ Deleted: {topic}")
        except Exception as e:
            print(f"   ⚠️ Failed to delete {topic}: {e}")

    print("⏳ Waiting 5s for deletion to propagate...")
    time.sleep(5)

    # 3. Recreate
    print("✨ Re-creating topics...")
    new_topics = [
        NewTopic(topic, num_partitions=1, replication_factor=3) 
        for topic in topics_to_reset
    ]
    
    fs = admin_client.create_topics(new_topics)
    
    for topic, f in fs.items():
        try:
            f.result()
            print(f"   ✅ Created: {topic}")
        except Exception as e:
            print(f"   ❌ Failed to create {topic}: {e}")

    print("🏁 Done! All events cleared.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to DELETE ALL DATA in these topics? (y/n): ")
    if confirm.lower() == 'y':
        reset_kafka_topics()
    else:
        print("Cancelled.")
