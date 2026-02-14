from shared.kafka.client import KafkaClient
import json
import time
from abc import ABC, abstractmethod
import traceback

class BaseAgentConsumer(ABC):
    def __init__(self, group_id: str, topics: list[str]):
        """
        Initialize the Kafka Consumer.
        :param group_id: The consumer group ID (e.g., 'triager-group')
        :param topics: List of topics to subscribe to
        """
        self.kafka_client = KafkaClient()
        self.consumer = self.kafka_client.create_consumer(group_id)
        
        # Subscribe with assignment callback
        self.consumer.subscribe(topics, on_assign=self._on_assign, on_revoke=self._on_revoke)
        self.topics = topics
        self.running = True
        print(f"👂 Agent Listening on topics: {topics} (Group: {group_id})")

    def _on_assign(self, consumer, partitions):
        print(f"🟢 Kafka Assigned Partitions: {[p.topic for p in partitions]}")
    
    def _on_revoke(self, consumer, partitions):
        print(f"🔴 Kafka Revoked Partitions: {[p.topic for p in partitions]}") 

    @abstractmethod
    def process_message(self, message: dict):
        """
        Process the parsed JSON message.
        Must be implemented by the specific Agent.
        """
        pass

    def run(self):
        """
        Start the infinite consumption loop.
        """
        try:
            print("⏳ Polling Loop Started...")
            while self.running:
                msg = self.consumer.poll(1.0) # Poll with 1s timeout

                if msg is None:
                    # print("zzZ...", end="\r") # Optional heartbeat
                    continue
                if msg.error():
                    print(f"⚠️ Consumer error: {msg.error()}")
                    continue
                
                print(f"📥 Received Raw Message! (Offset: {msg.offset()})")

                print(f"📥 Raw Message Received: {len(msg.value())} bytes")
                
                try:
                    # Parse Message
                    payload = msg.value().decode('utf-8')
                    data = json.loads(payload)
                    
                    print(f"📨 Received Event: {data.get('event', 'Unknown')} | Topic: {msg.topic()}")
                    
                    # Process
                    self.process_message(data)
                    
                    # Commit offset manually (or auto, but depending on config. We used default auto-commit)
                    # For safety in production we might want manual, but for now strict At-Least-Once via auto is fine.
                    
                except json.JSONDecodeError:
                    print(f"❌ Failed to decode JSON: {msg.value()}")
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    traceback.print_exc()

        except KeyboardInterrupt:
            print("🛑 Stopping consumer...")
        finally:
            self.consumer.close()
