from shared.kafka.client import KafkaClient
from shared.neo4j.client import Neo4jClient

def main():
    print("Agent 2: Review Manager Starting...")
    kafka = KafkaClient()
    neo4j = Neo4jClient()
    # TODO: Implement consumption from dev.pr.updates

if __name__ == "__main__":
    main()
