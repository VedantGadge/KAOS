from shared.kafka.client import KafkaClient
from shared.neo4j.client import Neo4jClient

def main():
    print("Agent 3: Ops Manager Starting...")
    kafka = KafkaClient()
    neo4j = Neo4jClient()
    # TODO: Implement consumption from ops.deploy.status

if __name__ == "__main__":
    main()
