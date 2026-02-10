from confluent_kafka.admin import AdminClient, NewTopic
from config.settings import settings

def create_topics():
    admin_client = AdminClient({
        'bootstrap.servers': settings.BOOTSTRAP_SERVERS,
        'security.protocol': settings.SECURITY_PROTOCOL,
        'sasl.mechanism': settings.SASL_MECHANISM,
        'sasl.username': settings.SASL_USERNAME,
        'sasl.password': settings.SASL_PASSWORD,
    })

    topics = [
        NewTopic("system.quality.reports", num_partitions=3, replication_factor=3),
        NewTopic("dev.pr.updates", num_partitions=3, replication_factor=3),
        NewTopic("ops.deploy.status", num_partitions=3, replication_factor=3)
    ]

    # Note: On Confluent Cloud Standard/Basic, replication factor is usually 3 by default. 
    # If this fails, try replication_factor=1 or remove it (let server decide).
    
    fs = admin_client.create_topics(topics)

    for topic, f in fs.items():
        try:
            f.result()  # The result itself is None
            print(f"✅ Topic created: {topic}")
        except Exception as e:
            print(f"⚠️ Failed to create topic {topic}: {e}")

if __name__ == "__main__":
    create_topics()
