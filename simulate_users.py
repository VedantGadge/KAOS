"""
Script to simulate multiple service owners using Slack CHANNELS as "users"
"""
from shared.neo4j.client import Neo4jClient

neo4j = Neo4jClient()

# Define mock users as the name of the CHANNEL they represent
# Make sure to invite the @KAOS bot to these channels first!
mock_setup = [
    {"name": "Alice", "service": "AuthService", "slack_channel": "#alice"},
    {"name": "Bob", "service": "CheckoutService", "slack_channel": "#bob"},
    {"name": "Charlie", "service": "PaymentService", "slack_channel": "#charlie"}
]

try:
    print("🧹 Cleaning up old mock data...")
    neo4j.query("MATCH (p:Person) WHERE p.name IN ['Alice', 'Bob', 'Charlie'] DETACH DELETE p")

    for user in mock_setup:
        print(f"👤 Creating mock owner: {user['name']} for {user['service']} -> Channel: {user['slack_channel']}...")
        
        # Create person and owner relationship
        # Note: We store the channel name in the slack_id field for this simulation
        query = """
        MERGE (p:Person {name: $name})
        SET p.slack_id = $slack_channel, p.status = 'Active'
        MERGE (s:Service {name: $service})
        MERGE (p)-[:OWNS]->(s)
        """
        neo4j.query(query, {
            "name": user['name'],
            "slack_channel": user['slack_channel'],
            "service": user['service']
        })
    
    print("\n✅ Simulation Setup Complete!")
    print("Mappings created:")
    for user in mock_setup:
         print(f"  - {user['service']} -> {user['name']} ({user['slack_channel']})")
    
    print("\nNext Steps:")
    print("1. Create channels #alice, #bob, and #charlie in Slack.")
    print("2. Invite your bot to each channel: /invite @KAOS")

    neo4j.close()
except Exception as e:
    print(f"Error: {e}")
