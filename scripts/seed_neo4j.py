from shared.neo4j.client import Neo4jClient

def seed_data():
    client = Neo4jClient()
    print("🌱 Seeding Neo4j Database...")

    # Clear existing data (optional, be careful in prod!)
    client.query("MATCH (n) DETACH DELETE n")
    print("🗑️ Cleared existing data.")

    # Create Services
    client.query("CREATE (:Service {name: 'PaymentService'})")
    client.query("CREATE (:Service {name: 'AuthService'})")
    
    # Create People
    # 1. Alice (Manager, Active)
    client.query("CREATE (:Person {name: 'Alice', role: 'Manager', status: 'Active', slack_id: 'U12345', email: 'alice@kaos.com'})")
    
    # 2. Bob (Developer, On_Leave) - Owns PaymentService
    client.query("CREATE (:Person {name: 'Bob', role: 'Developer', status: 'On_Leave', slack_id: 'U67890', email: 'bob@kaos.com'})")
    
    # 3. Charlie (Developer, Active) - Worked on PaymentService
    client.query("CREATE (:Person {name: 'Charlie', role: 'Developer', status: 'Active', slack_id: 'U11223', email: 'charlie@kaos.com'})")

    # Relationships
    
    # Bob OWNS PaymentService
    client.query("""
        MATCH (p:Person {name: 'Bob'}), (s:Service {name: 'PaymentService'})
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

    print("✅ Seeding Complete!")
    print("Scenario Created:")
    print("- Service: PaymentService")
    print("- Owner: Bob (On_Leave)")
    print("- Contributor: Charlie (Active)")
    print("- Manager: Alice (Active)")
    
    client.close()

if __name__ == "__main__":
    seed_data()
