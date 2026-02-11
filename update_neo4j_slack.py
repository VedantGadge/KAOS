"""
Update Neo4j with the CORRECT real User ID for DM testing
"""
from shared.neo4j.client import Neo4jClient

neo4j = Neo4jClient()

try:
    print("Updating Neo4j with the CORRECT User ID (U0AE4395S6P)...")
    
    # Update person 'Charlie' to have the user's real Slack ID
    update_query = """
    MATCH (p:Person {name: 'Charlie'})
    SET p.slack_id = 'U0AE4395S6P'
    RETURN p.name, p.slack_id
    """
    res = neo4j.query(update_query)
    if res:
        print(f"✅ Updated {res[0]['p.name']} with Slack ID: {res[0]['p.slack_id']}")
    else:
        print("Charlie not found.")

    neo4j.close()
except Exception as e:
    print(f"Error: {e}")
