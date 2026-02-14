import sys
import os

# Add the parent directory to sys.path to allow imports from shared
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logger import event_logger
import json

def seed_data():
    """Seed the database with some sample data for demonstration."""
    print("🌱 Seeding database with sample PR events...")
    
    # PR #101 Context: Missing Tests
    pr_id = "101"
    repo = "PaymentService"
    
    event_logger.log_event("PR_CREATED", "Dev-Alice", repo, pr_id, {"title": "Add Apple Pay support"})
    event_logger.log_event("PR_STATUS_CHECK", "Agent", repo, pr_id, {"status": "CLEAN"})
    event_logger.log_event("REVIEW_ASSIGNED", "Agent", repo, pr_id, {"reviewer": "Senior-Bob", "role": "Owner"})
    event_logger.log_event("REVIEW_REJECTED", "Senior-Bob", repo, pr_id, {"reason": "Missing unit tests for new payment provider"})
    event_logger.log_event("DEV_PUSH", "Dev-Alice", repo, pr_id, {"commit": "Added unit tests"})
    event_logger.log_event("REVIEW_APPROVED", "Senior-Bob", repo, pr_id, {"comment": "Looks good now"})
    event_logger.log_event("PR_MERGED", "Agent", repo, pr_id, {"strategy": "Squash"})

    # Bug Report Context - Auto-embedding generation test
    # We do NOT provide 'embedding' arg here, expecting EventLogger to generate it via Bedrock
    event_logger.log_event("NOTION_TICKET_CREATED", "Agent", "AuthService", None, 
        details={
            "title": "NPE in Login",
            "intro": "NullPointerException when user tries to login with Google",
            "severity": "HIGH",
            "description": "Stack trace: NullPointerException at AuthService.java:42... happens when email is null."
        }
    )

def simulate_chatbot_query(user_question: str):
    print(f"\n👤 User: {user_question}")
    
    # 1. Check for PR ID
    import re
    match = re.search(r"#(\d+)", user_question)
    if match:
        pr_id = match.group(1)
        print("🤖 Bot (Internal Thought): Finding PR logs...")
        print(f"🤖 Bot (Action): SELECT * FROM pr_events WHERE pr_id = '{pr_id}'")
        logs = event_logger.get_logs_for_pr(pr_id)
        # ... (display logs logic) ...
    
    # 2. Check for "Bug" keyword for semantic search simulation
    elif "bug" in user_question.lower():
        print("🤖 Bot (Internal Thought): User is asking about bugs. I need to search the 'details' column for keywords.")
        print(f"🤖 Bot (Action): Querying database for bugs with keywords...")
        
        # Use a new method we will add to EventLogger, or just manual session query here?
        # For demo simplicity, let's access the engine/session directly effectively, 
        # OR better yet, let's just stick to the abstraction if possible, but we don't have a search method yet.
        # Let's add a search method to the Logger class in the next step or just use raw SQL via engine.
        
        # Accessing via the exposed engine for raw SQL for the demo to show versatility
        with event_logger.engine.connect() as conn:
             from sqlalchemy import text
             # Note: JSON extraction syntax varies by DB (SQLite vs Postgres). 
             # For this demo which defaults to SQLite, we treat details as Text.
             result = conn.execute(text("SELECT details FROM pr_events WHERE event_type LIKE '%TICKET%'"))
             rows = result.fetchall()

        found = []
        for row in rows:
            # row[0] is the details string
            try:
                details = json.loads(row[0])
                if "NPE" in details.get("title", "") or "NPE" in details.get("description", ""):
                    found.append(details)
            except:
                continue
        
        if found:
            print(f"🤖 Bot (Response): Yes, a similar bug was reported recently:")
            for bug in found:
                print(f"   - **{bug['title']}** (Severity: {bug['severity']})")
                print(f"     Description: {bug['description'][:60]}...")
        else:
             print("🤖 Bot: No similar bugs found.")

    else:
        print("🤖 Bot: I didn't understand the question.")

if __name__ == "__main__":
    # Ensure fresh DB for demo
    if os.path.exists("kaos_events.db"):
        # Dispose the engine to release the file lock
        event_logger.engine.dispose()
        try:
            os.remove("kaos_events.db")
            print("🗑️  Deleted old DB file.")
        except PermissionError:
            print("⚠️ Could not delete DB file (locked). Using existing DB.")
    
    # Re-create tables (critical because we might have just deleted the file!)
    from shared.logger import Base
    Base.metadata.create_all(event_logger.engine)
    print("✨ re-initialized DB schema.")

    seed_data()
    simulate_chatbot_query("Why was PR #101 rejected?")
    simulate_chatbot_query("Have we seen any NPE bugs?")
