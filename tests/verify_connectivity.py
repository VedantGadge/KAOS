from shared.kafka.client import KafkaClient
from shared.neo4j.client import Neo4jClient
import sys

def verify_kafka():
    print("Verifying Kafka Connection...")
    try:
        client = KafkaClient()
        producer = client.create_producer()
        cluster_meta = producer.list_topics(timeout=10)
        print(f"✅ Connected to Confluent Cloud! Found {len(cluster_meta.topics)} topics.")
    except Exception as e:
        print(f"❌ Kafka Connection Failed: {e}")
        print(f"❌ Kafka Connection Failed: {e}")
        # sys.exit(1)

def verify_neo4j():
    print("Verifying Neo4j Connection...")
    try:
        client = Neo4jClient()
        result = client.query("RETURN 1 AS num")
        if result and result[0]['num'] == 1:
            print("✅ Connected to Neo4j Aura!")
        else:
             print("❌ Neo4j Connection Failed: Unexpected result.")
        client.close()
    except Exception as e:
        print(f"❌ Neo4j Connection Failed: {e}")
if __name__ == "__main__":
    verify_kafka()
    print("-" * 20)
    verify_neo4j()
