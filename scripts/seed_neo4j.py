from shared.neo4j.client import Neo4jClient

def seed_data():
    client = Neo4jClient()
    print("🌱 Seeding Neo4j Database...")

    # Clear existing data (optional, be careful in prod!)
    client.query("MATCH (n) DETACH DELETE n")
    print("🗑️ Cleared existing data.")

    # Create Services
    client.query("CREATE (:Service {name: 'PaymentService', repo_url: 'https://github.com/kaos/PaymentService', tier: 1})")
    client.query("CREATE (:Service {name: 'AuthService', repo_url: 'https://github.com/kaos/AuthService', tier: 1})")
    
    # Create People
    # 1. Alice (Senior Engineer, Active) - Owns AuthService
    client.query("CREATE (:Person {name: 'Alice', role: 'Senior', status: 'Active', slack_id: '#alice', email: 'alice@kaos.com'})")
    
    # 2. Bob (Junior Developer, On_Leave) - Owns PaymentService
    client.query("CREATE (:Person {name: 'Bob', role: 'Junior', status: 'On_Leave', slack_id: '#bob', email: 'bob@kaos.com'})")
    
    # 3. Charlie (Junior Developer, Active) - Worked on PaymentService
    client.query("CREATE (:Person {name: 'Charlie', role: 'Junior', status: 'Active', slack_id: '#charlie', email: 'charlie@kaos.com'})")

    # 4. Dave (Senior Engineer, Active) - Owns PaymentService (for reviewer scenarios)
    client.query("CREATE (:Person {name: 'Dave', role: 'Senior', status: 'Active', slack_id: '#dave', email: 'dave@kaos.com'})")

    # Relationships
    
    # Bob OWNS PaymentService
    client.query("""
        MATCH (p:Person {name: 'Bob'}), (s:Service {name: 'PaymentService'})
        MERGE (p)-[:OWNS]->(s)
    """)

    # Dave OWNS PaymentService (Senior, can review)
    client.query("""
        MATCH (p:Person {name: 'Dave'}), (s:Service {name: 'PaymentService'})
        MERGE (p)-[:OWNS]->(s)
    """)

    # Alice OWNS AuthService
    client.query("""
        MATCH (p:Person {name: 'Alice'}), (s:Service {name: 'AuthService'})
        MERGE (p)-[:OWNS]->(s)
    """)
    
    # Charlie WORKED_ON PaymentService
    client.query("""
        MATCH (p:Person {name: 'Charlie'}), (s:Service {name: 'PaymentService'})
        MERGE (p)-[:WORKED_ON]->(s)
    """)
    
    # Bob REPORTS_TO Alice
    client.query("""
        MATCH (bob:Person {name: 'Bob'}), (alice:Person {name: 'Alice'})
        MERGE (bob)-[:REPORTS_TO]->(alice)
    """)

    # Charlie REPORTS_TO Dave
    client.query("""
        MATCH (charlie:Person {name: 'Charlie'}), (dave:Person {name: 'Dave'})
        MERGE (charlie)-[:REPORTS_TO]->(dave)
    """)

    print("✅ Seeding Complete!")
    print("Scenario Created:")
    print("- Services: PaymentService, AuthService")
    print("- Alice: Senior, Active, Owns AuthService")
    print("- Bob: Junior, On_Leave, Owns PaymentService")
    print("- Charlie: Junior, Active, Worked on PaymentService")
    print("- Dave: Senior, Active, Owns PaymentService (reviewer)")
    
    client.close()

if __name__ == "__main__":
    seed_data()

