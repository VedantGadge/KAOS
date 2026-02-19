import sys
import os
import sqlite3
from sqlalchemy import create_engine, MetaData

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from scripts.reset_kafka import reset_kafka_topics

def reset_database():
    print("🗑️  CLEARING LOCAL DATABASE (kaos_events.db)...")
    db_path = "kaos_events.db"
    
    if not os.path.exists(db_path):
        print("   ⚠️ Database file not found. Skipping.")
        return

    try:
        # Use simple sqlite connector for truncation
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        tables = ["jira_tickets", "notion_tickets", "pr_events"]
        
        for table in tables:
            try:
                cursor.execute(f"DELETE FROM {table}")
                print(f"   ✅ Cleared table: {table}")
            except sqlite3.OperationalError as e:
                print(f"   ⚠️ Could not clear {table}: {e}")
                
        conn.commit()
        conn.close()
        print("✨ Database cleared.")
        
    except Exception as e:
        print(f"❌ Failed to clear database: {e}")

def main():
    print("\n⚠️  WARNING: THIS WILL DELETE ALL DATA (Local DB + Kafka Events)")
    print("   Use this to reset the demo state completely.\n")
    
    confirm = input("Are you sure? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return

    # 1. Clear Database
    reset_database()
    
    print("\n🔥 CLEARING KAFKA TOPICS...")
    try:
        reset_kafka_topics()
    except Exception as e:
        print(f"❌ Failed to reset Kafka: {e}")

    # 3. Seed Neo4j (to ensure new 'dev_user' is present)
    print("\n🌱 SEEDING NEO4J DATABASE...")
    try:
        # Import and run directly if possible, or subprocess
        from scripts.seed_neo4j import main as seed_main
        seed_main() 
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "scripts/seed_neo4j.py"])
    except Exception as e:
         print(f"❌ Failed to seed Neo4j: {e}")
        
    print("\n✅ SYSTEM RESET COMPLETE.")
    print("You can now restart the agents and run the demo from scratch.")

if __name__ == "__main__":
    main()
