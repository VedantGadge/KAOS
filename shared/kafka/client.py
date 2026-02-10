from confluent_kafka import Producer, Consumer
from config.settings import settings
import json

class KafkaClient:
    def __init__(self):
        self.conf = {
            'bootstrap.servers': settings.BOOTSTRAP_SERVERS,
            'security.protocol': settings.SECURITY_PROTOCOL,
            'sasl.mechanism': settings.SASL_MECHANISM,
            'sasl.username': settings.SASL_USERNAME,
            'sasl.password': settings.SASL_PASSWORD,
        }

    def create_producer(self):
        return Producer(self.conf)

    def create_consumer(self, group_id: str):
        consumer_conf = self.conf.copy()
        consumer_conf.update({
            'group.id': group_id,
            'auto.offset.reset': 'earliest'
        })
        return Consumer(consumer_conf)
