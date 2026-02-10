from shared.kafka.client import KafkaClient
from shared.models.events import ReportEvent
from datetime import datetime
import json
import uuid

def produce_test_report():
    kafka = KafkaClient()
    producer = kafka.create_producer()
    
    event = ReportEvent(
        event_id=str(uuid.uuid4()),
        service_name="PaymentService",
        severity="CRITICAL",
        error_message="NullPointerException in ProcessTransaction",
        stack_trace="at com.kaos.payment.ProcessTransaction(Payment.java:42)",
        timestamp=datetime.now()
    )

    topic = "system.quality.reports"
    print(f"🚀 Sending test event to {topic}...")
    
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
    produce_test_report()
