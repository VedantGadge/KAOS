from confluent_kafka import Producer, Consumer
from config.settings import settings
import json
import certifi
class KafkaClient:
    def __init__(self):
        self.conf = {
            'bootstrap.servers': settings.BOOTSTRAP_SERVERS,
        }
        if settings.SECURITY_PROTOCOL:
            self.conf['security.protocol'] = settings.SECURITY_PROTOCOL
        if settings.SASL_MECHANISM:
            self.conf['sasl.mechanism'] = settings.SASL_MECHANISM
        if settings.SASL_USERNAME:
            self.conf['sasl.username'] = settings.SASL_USERNAME
        if settings.SASL_PASSWORD:
            self.conf['sasl.password'] = settings.SASL_PASSWORD
            
        # Fix for AWS Lambda (Amazon Linux 2023) SSL verification
        self.conf['ssl.ca.location'] = certifi.where()

    def create_producer(self):
        return Producer(self.conf)

    def create_consumer(self, group_id: str):
        consumer_conf = self.conf.copy()
        consumer_conf.update({
            'group.id': group_id,
            'auto.offset.reset': 'earliest'
        })
        return Consumer(consumer_conf)
