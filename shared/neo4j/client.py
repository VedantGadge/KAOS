from neo4j import GraphDatabase
from config.settings import settings

class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def query(self, query: str, parameters: dict = None):
        with self.driver.session() as session:
            return session.run(query, parameters).data()
