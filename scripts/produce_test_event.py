from shared.kafka.client import KafkaClient
from shared.models.events import ReportEvent
from datetime import datetime
import json
import uuid

import argparse

def produce_test_report(service_name="PaymentService"):
    kafka = KafkaClient()
    producer = kafka.create_producer()
    
    event = ReportEvent(
        event_id=str(uuid.uuid4()),
        service_name=service_name,
        severity="CRITICAL",
        error_message=f"NullPointerException in {service_name}",
        stack_trace=f"at com.kaos.{service_name.lower()}.Process(Source.java:42)",
        timestamp=datetime.now()
    )

    topic = "system.quality.reports"
    print(f"🚀 Sending test event for {service_name} to {topic}...")
    
    # Serialize Pydantic model to JSON
    value = event.model_dump_json()
    
    def delivery_report(err, msg):
        if err is not None:
            print(f"❌ Message delivery failed: {err}")
        else:
            print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}]")

    producer.produce(topic, value.encode('utf-8'), callback=delivery_report)
    producer.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default="PaymentService")
    args = parser.parse_args()
    produce_test_report(args.service)
