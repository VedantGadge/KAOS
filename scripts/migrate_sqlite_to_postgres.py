import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logger import EventLogger, PREvent, NotionTicket, JiraTicket
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def migrate_data():
    print("🚀 Starting Migration from SQLite to Postgres...")

    # 1. Connect to SQLite (Source)
    sqlite_conn = "sqlite:///kaos_events.db"
    if not os.path.exists("kaos_events.db"):
        print("❌ Could not find kaos_events.db. Nothing to migrate.")
        return

    sqlite_logger = EventLogger(sqlite_conn)
    sqlite_session = sqlite_logger.Session()

    # 2. Connect to Postgres (Destination)
    pg_conn = os.getenv("DATABASE_URL", "postgresql://kaos_user:kaos_password@localhost:5432/kaos_events")
    pg_logger = EventLogger(pg_conn)
    pg_session = pg_logger.Session()

    print(f"🔌 Connected to Source: SQLite")
    print(f"🔌 Connected to Dest: Postgres")

    try:
        # Migrate PR Events
        events = sqlite_session.query(PREvent).all()
        print(f"📦 Found {len(events)} PREvent records. Migrating...")
        for e in events:
            # We copy fields manually to avoid ID conflicts or SQLAlchemy binding issues
            new_event = PREvent(
                timestamp=e.timestamp,
                event_type=e.event_type,
                pr_id=e.pr_id,
                repo=e.repo,
                actor=e.actor,
                details=e.details,
            )
            # The embedding in SQLite was stored as a JSON string (Text)
            # pgvector Vector expects a list of floats or numpy array or string formatted like '[1,2,3]'
            # Since JSON serialization of a float list is exactly '[1,2,3]', we can pass it directly
            # if it's not None.
            if e.embedding:
                try:
                    import json
                    new_event.embedding = json.loads(e.embedding)
                except:
                    new_event.embedding = None
                    
            pg_session.add(new_event)
        
        # Migrate Notion Tickets
        notion_tickets = sqlite_session.query(NotionTicket).all()
        print(f"📦 Found {len(notion_tickets)} NotionTicket records. Migrating...")
        for t in notion_tickets:
            new_t = NotionTicket(
                service=t.service,
                page_id=t.page_id,
                status=t.status,
                title=t.title,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            pg_session.add(new_t)

        # Migrate Jira Tickets
        jira_tickets = sqlite_session.query(JiraTicket).all()
        print(f"📦 Found {len(jira_tickets)} JiraTicket records. Migrating...")
        for t in jira_tickets:
            new_t = JiraTicket(
                service=t.service,
                issue_key=t.issue_key,
                status=t.status,
                summary=t.summary,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            pg_session.add(new_t)

        pg_session.commit()
        print("✅ Migration complete successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        pg_session.rollback()
    finally:
        sqlite_session.close()
        pg_session.close()

if __name__ == "__main__":
    migrate_data()
